import json
import logging
import zipfile
import os
from typing import Dict, Any, Optional, List
from .aws_config import get_lambda_client, get_s3_client

logger = logging.getLogger(__name__)

class LambdaManager:
    """Utility class for managing AWS Lambda functions."""
    
    def __init__(self):
        self.lambda_client = get_lambda_client()
        self.s3_client = get_s3_client()
    
    def create_deployment_package(self, function_dir: str, output_path: str) -> str:
        """
        Create a deployment package (ZIP file) for a Lambda function.
        
        Args:
            function_dir: Directory containing the Lambda function code
            output_path: Path where the ZIP file should be created
        
        Returns:
            Path to the created ZIP file
        """
        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(function_dir):
                    for file in files:
                        if file.endswith('.py') or file.endswith('.json'):
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, function_dir)
                            zipf.write(file_path, arcname)
            
            logger.info(f"Created deployment package: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating deployment package: {str(e)}")
            raise
    
    def create_function(self, function_name: str, runtime: str, handler: str,
                       zip_file_path: str, role_arn: str = "arn:aws:iam::000000000000:role/lambda-role",
                       timeout: int = 300, memory_size: int = 128,
                       environment_variables: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Create a Lambda function.
        
        Args:
            function_name: Name of the function
            runtime: Python runtime (e.g., 'python3.9')
            handler: Handler function (e.g., 'lambda_function.lambda_handler')
            zip_file_path: Path to the deployment package
            role_arn: IAM role ARN (use dummy ARN for LocalStack)
            timeout: Function timeout in seconds
            memory_size: Memory allocation in MB
            environment_variables: Environment variables
        
        Returns:
            Function configuration
        """
        try:
            # Read the ZIP file
            with open(zip_file_path, 'rb') as f:
                zip_content = f.read()
            
            # Prepare function configuration
            function_config = {
                'FunctionName': function_name,
                'Runtime': runtime,
                'Role': role_arn,
                'Handler': handler,
                'Code': {'ZipFile': zip_content},
                'Timeout': timeout,
                'MemorySize': memory_size
            }
            
            if environment_variables:
                function_config['Environment'] = {
                    'Variables': environment_variables
                }
            
            response = self.lambda_client.create_function(**function_config)
            
            logger.info(f"Created Lambda function: {function_name}")
            return response
            
        except Exception as e:
            logger.error(f"Error creating function {function_name}: {str(e)}")
            raise
    
    def update_function(self, function_name: str, zip_file_path: str) -> Dict[str, Any]:
        """
        Update a Lambda function with new code.
        
        Args:
            function_name: Name of the function
            zip_file_path: Path to the new deployment package
        
        Returns:
            Updated function configuration
        """
        try:
            with open(zip_file_path, 'rb') as f:
                zip_content = f.read()
            
            response = self.lambda_client.update_function_code(
                FunctionName=function_name,
                ZipFile=zip_content
            )
            
            logger.info(f"Updated Lambda function: {function_name}")
            return response
            
        except Exception as e:
            logger.error(f"Error updating function {function_name}: {str(e)}")
            raise
    
    def invoke_function(self, function_name: str, payload: Dict[str, Any],
                       invocation_type: str = 'RequestResponse') -> Dict[str, Any]:
        """
        Invoke a Lambda function.
        
        Args:
            function_name: Name of the function
            payload: Function payload
            invocation_type: Invocation type ('RequestResponse' or 'Event')
        
        Returns:
            Function response
        """
        try:
            response = self.lambda_client.invoke(
                FunctionName=function_name,
                InvocationType=invocation_type,
                Payload=json.dumps(payload)
            )
            
            # Parse response payload
            if 'Payload' in response:
                payload_bytes = response['Payload'].read()
                if payload_bytes:
                    response['Payload'] = json.loads(payload_bytes.decode('utf-8'))
            
            logger.info(f"Invoked Lambda function: {function_name}")
            return response
            
        except Exception as e:
            logger.error(f"Error invoking function {function_name}: {str(e)}")
            raise
    
    def delete_function(self, function_name: str) -> bool:
        """
        Delete a Lambda function.
        
        Args:
            function_name: Name of the function
        
        Returns:
            True if successful
        """
        try:
            self.lambda_client.delete_function(FunctionName=function_name)
            logger.info(f"Deleted Lambda function: {function_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting function {function_name}: {str(e)}")
            return False
    
    def list_functions(self) -> List[Dict[str, Any]]:
        """
        List all Lambda functions.
        
        Returns:
            List of function configurations
        """
        try:
            response = self.lambda_client.list_functions()
            functions = response.get('Functions', [])
            logger.info(f"Found {len(functions)} Lambda functions")
            return functions
        except Exception as e:
            logger.error(f"Error listing functions: {str(e)}")
            return []

# Example usage for deploying the text processor
def deploy_text_processor():
    """Deploy the text processor Lambda function."""
    lambda_manager = LambdaManager()
    
    # Create deployment package
    function_dir = "lambda_functions"
    zip_path = "text_processor.zip"
    
    try:
        # Create deployment package
        lambda_manager.create_deployment_package(function_dir, zip_path)
        
        # Deploy function
        function_config = lambda_manager.create_function(
            function_name="text-processor",
            runtime="python3.9",
            handler="text_processor.lambda_handler",
            zip_file_path=zip_path,
            timeout=300,
            memory_size=512,
            environment_variables={
                'CHUNK_SIZE': '1000',
                'PCA_COMPONENTS': '256'
            }
        )
        
        logger.info("Successfully deployed text processor Lambda function")
        return function_config
        
    except Exception as e:
        logger.error(f"Error deploying text processor: {str(e)}")
        raise
    finally:
        # Clean up ZIP file
        if os.path.exists(zip_path):
            os.remove(zip_path) 