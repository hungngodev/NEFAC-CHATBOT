"""
STAGE 1: Document Receiver Lambda
Triggered by S3 upload events. Validates document and sends to parsing queue.
"""
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict

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
PARSING_QUEUE_URL = os.environ['PARSING_QUEUE_URL']
TRACKING_TABLE_NAME = os.environ.get('TRACKING_TABLE_NAME', 'nefac-document-tracking')
MAX_FILE_SIZE_MB = int(os.environ.get('MAX_FILE_SIZE_MB', '100'))
ALLOWED_MIME_TYPES = os.environ.get(
    'ALLOWED_MIME_TYPES',
    'application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain'
).split(',')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle S3 upload events and route documents to parsing queue.
    
    Args:
        event: S3 event notification
        context: Lambda context
        
    Returns:
        Response with processing status
    """
    try:
        # Extract S3 event details
        for record in event.get('Records', []):
            if record.get('eventName', '').startswith('ObjectCreated'):
                process_document(record['s3'])
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Documents processed successfully'})
        }
    
    except Exception as e:
        logger.error(f"Error in document receiver: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def process_document(s3_event: Dict[str, Any]) -> None:
    """
    Process a single document upload.
    
    Args:
        s3_event: S3 event data
    """
    bucket = s3_event['bucket']['name']
    key = s3_event['object']['key']
    size_bytes = s3_event['object']['size']
    
    # Generate unique IDs
    document_id = str(uuid.uuid4())
    correlation_id = f"doc-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    
    logger.info(f"Processing document: {key} (correlation_id={correlation_id})")
    
    try:
        # Get object metadata
        head_response = s3_client.head_object(Bucket=bucket, Key=key)
        content_type = head_response.get('ContentType', 'application/octet-stream')
        
        # Validate file size
        size_mb = size_bytes / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            raise ValueError(f"File size ({size_mb:.2f}MB) exceeds maximum ({MAX_FILE_SIZE_MB}MB)")
        
        # Validate MIME type
        if content_type not in ALLOWED_MIME_TYPES and not any(
            content_type.startswith(allowed.split('/')[0]) for allowed in ALLOWED_MIME_TYPES
        ):
            raise ValueError(f"Unsupported file type: {content_type}")
        
        # Create tracking record in DynamoDB
        table = dynamodb.Table(TRACKING_TABLE_NAME)
        table.put_item(
            Item={
                'document_id': document_id,
                'correlation_id': correlation_id,
                's3_bucket': bucket,
                's3_key': key,
                'filename': key.split('/')[-1],
                'mime_type': content_type,
                'size_bytes': size_bytes,
                'status': 'RECEIVED',
                'stage': 'receiver',
                'uploaded_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'retry_count': 0
            }
        )
        
        # Send message to parsing queue
        message_body = {
            'correlation_id': correlation_id,
            'document_id': document_id,
            's3_bucket': bucket,
            's3_key': key,
            'metadata': {
                'filename': key.split('/')[-1],
                'mime_type': content_type,
                'size_bytes': size_bytes,
                'uploaded_at': datetime.utcnow().isoformat()
            },
            'stage': 'parsing',
            'retry_count': 0,
            'previous_stage_duration_ms': 0
        }
        
        response = sqs_client.send_message(
            QueueUrl=PARSING_QUEUE_URL,
            MessageBody=json.dumps(message_body),
            MessageAttributes={
                'correlation_id': {
                    'StringValue': correlation_id,
                    'DataType': 'String'
                },
                'document_id': {
                    'StringValue': document_id,
                    'DataType': 'String'
                }
            }
        )
        
        logger.info(
            f"Document {document_id} sent to parsing queue. "
            f"MessageId={response['MessageId']}"
        )
        
    except (ClientError, ValueError) as e:
        logger.error(f"Error processing document {key}: {str(e)}")
        # Update DynamoDB with error status
        try:
            table = dynamodb.Table(TRACKING_TABLE_NAME)
            table.put_item(
                Item={
                    'document_id': document_id,
                    'correlation_id': correlation_id,
                    's3_bucket': bucket,
                    's3_key': key,
                    'status': 'FAILED',
                    'stage': 'receiver',
                    'error': str(e),
                    'updated_at': datetime.utcnow().isoformat()
                }
            )
        except Exception as db_error:
            logger.error(f"Error updating DynamoDB: {str(db_error)}")
        
        raise
