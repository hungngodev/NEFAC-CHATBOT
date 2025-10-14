"""
STAGE 2: Document Parser Lambda
Triggered by parsing_queue. Parses documents using LlamaParse/Unstructured.
"""
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')

# Environment variables
CHUNKING_QUEUE_URL = os.environ['CHUNKING_QUEUE_URL']
TRACKING_TABLE_NAME = os.environ.get('TRACKING_TABLE_NAME', 'nefac-document-tracking')
PARSED_TEXT_BUCKET = os.environ['PARSED_TEXT_BUCKET']
LLAMAPARSE_API_KEY = os.environ.get('LLAMAPARSE_API_KEY')
USE_LLAMAPARSE = os.environ.get('USE_LLAMAPARSE', 'false').lower() == 'true'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Parse documents from SQS messages.
    
    Args:
        event: SQS event with document references
        context: Lambda context
        
    Returns:
        Batch response for SQS
    """
    start_time = time.time()
    batch_item_failures = []
    
    for record in event['Records']:
        try:
            process_message(record, start_time)
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            # Return message ID to retry
            batch_item_failures.append({"itemIdentifier": record['messageId']})
    
    return {
        "batchItemFailures": batch_item_failures
    }


def process_message(record: Dict[str, Any], start_time: float) -> None:
    """Process a single SQS message."""
    message_body = json.loads(record['body'])
    correlation_id = message_body['correlation_id']
    document_id = message_body['document_id']
    s3_bucket = message_body['s3_bucket']
    s3_key = message_body['s3_key']
    
    logger.info(f"Parsing document: {document_id} (correlation_id={correlation_id})")
    
    try:
        # Update status to PARSING
        update_document_status(document_id, 'PARSING', 'parser')
        
        # Download document from S3
        temp_file_path = f"/tmp/{document_id}"
        s3_client.download_file(s3_bucket, s3_key, temp_file_path)
        
        # Parse document based on type
        mime_type = message_body['metadata']['mime_type']
        parsed_text = parse_document(temp_file_path, mime_type)
        
        if not parsed_text or len(parsed_text.strip()) == 0:
            raise ValueError("Parsing resulted in empty text")
        
        # Store parsed text in S3
        parsed_key = f"parsed/{document_id}.txt"
        s3_client.put_object(
            Bucket=PARSED_TEXT_BUCKET,
            Key=parsed_key,
            Body=parsed_text.encode('utf-8'),
            ContentType='text/plain',
            Metadata={
                'correlation_id': correlation_id,
                'document_id': document_id,
                'original_mime_type': mime_type
            }
        )
        
        # Calculate processing time
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Send to chunking queue
        next_message = {
            **message_body,
            'parsed_s3_bucket': PARSED_TEXT_BUCKET,
            'parsed_s3_key': parsed_key,
            'parsed_text_length': len(parsed_text),
            'stage': 'chunking',
            'previous_stage_duration_ms': duration_ms
        }
        
        sqs_client.send_message(
            QueueUrl=CHUNKING_QUEUE_URL,
            MessageBody=json.dumps(next_message),
            MessageAttributes={
                'correlation_id': {
                    'StringValue': correlation_id,
                    'DataType': 'String'
                }
            }
        )
        
        # Update status
        update_document_status(
            document_id,
            'PARSED',
            'parser',
            {
                'parsed_text_length': len(parsed_text),
                'duration_ms': duration_ms
            }
        )
        
        logger.info(f"Document {document_id} parsed successfully ({len(parsed_text)} chars)")
        
        # Clean up temp file
        os.remove(temp_file_path)
        
    except Exception as e:
        logger.error(f"Error parsing document {document_id}: {str(e)}")
        update_document_status(document_id, 'PARSE_FAILED', 'parser', {'error': str(e)})
        raise


def parse_document(file_path: str, mime_type: str) -> str:
    """
    Parse document based on MIME type.
    
    Args:
        file_path: Path to the document file
        mime_type: MIME type of the document
        
    Returns:
        Parsed text content
    """
    if USE_LLAMAPARSE and LLAMAPARSE_API_KEY:
        return parse_with_llamaparse(file_path)
    else:
        return parse_with_unstructured(file_path, mime_type)


def parse_with_llamaparse(file_path: str) -> str:
    """Parse document using LlamaParse."""
    try:
        from llama_parse import LlamaParse
        
        parser = LlamaParse(api_key=LLAMAPARSE_API_KEY)
        documents = parser.load_data(file_path)
        
        # Combine all document pages
        return "\n\n".join([doc.text for doc in documents])
    
    except ImportError:
        logger.warning("LlamaParse not available, falling back to unstructured")
        return parse_with_unstructured(file_path, 'application/pdf')


def parse_with_unstructured(file_path: str, mime_type: str) -> str:
    """Parse document using Unstructured.io."""
    try:
        from unstructured.partition.auto import partition
        
        elements = partition(filename=file_path)
        return "\n\n".join([str(el) for el in elements])
    
    except ImportError:
        logger.error("Unstructured.io not available")
        # Fallback to basic text extraction
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()


def update_document_status(
    document_id: str,
    status: str,
    stage: str,
    additional_data: Optional[Dict[str, Any]] = None
) -> None:
    """Update document tracking status in DynamoDB."""
    try:
        table = dynamodb.Table(TRACKING_TABLE_NAME)
        update_data = {
            'status': status,
            'stage': stage,
            'updated_at': datetime.utcnow().isoformat()
        }
        
        if additional_data:
            update_data.update(additional_data)
        
        table.update_item(
            Key={'document_id': document_id},
            UpdateExpression='SET ' + ', '.join([f'{k} = :{k}' for k in update_data.keys()]),
            ExpressionAttributeValues={f':{k}': v for k, v in update_data.items()}
        )
    except Exception as e:
        logger.error(f"Error updating DynamoDB: {str(e)}")
