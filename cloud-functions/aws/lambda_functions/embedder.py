"""
STAGE 4: Embedder Lambda
Triggered by embedding_queue (batched). Generates embeddings using OpenAI API.
"""
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')

# Environment variables
INDEXING_QUEUE_URL = os.environ['INDEXING_QUEUE_URL']
TRACKING_TABLE_NAME = os.environ.get('TRACKING_TABLE_NAME', 'nefac-document-tracking')
EMBEDDINGS_BUCKET = os.environ['EMBEDDINGS_BUCKET']
OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', 'text-embedding-3-small')
BATCH_SIZE = int(os.environ.get('EMBEDDING_BATCH_SIZE', '10'))


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Generate embeddings for chunks from SQS messages (batched).
    
    Args:
        event: SQS event with chunk references (batched 5-10 messages)
        context: Lambda context
        
    Returns:
        Batch response for SQS
    """
    start_time = time.time()
    batch_item_failures = []
    
    # Group messages by document_id for efficient processing
    messages_by_doc = {}
    for record in event['Records']:
        try:
            message_body = json.loads(record['body'])
            doc_id = message_body['document_id']
            if doc_id not in messages_by_doc:
                messages_by_doc[doc_id] = []
            messages_by_doc[doc_id].append((record, message_body))
        except Exception as e:
            logger.error(f"Error parsing message: {str(e)}")
            batch_item_failures.append({"itemIdentifier": record['messageId']})
    
    # Process each document's chunks
    for doc_id, messages in messages_by_doc.items():
        try:
            process_document_chunks(doc_id, messages, start_time)
        except Exception as e:
            logger.error(f"Error processing document {doc_id}: {str(e)}", exc_info=True)
            # Mark all messages for this document as failed
            for record, _ in messages:
                batch_item_failures.append({"itemIdentifier": record['messageId']})
    
    return {
        "batchItemFailures": batch_item_failures
    }


def process_document_chunks(
    document_id: str,
    messages: List[tuple],
    start_time: float
) -> None:
    """Process chunks for a single document."""
    correlation_id = messages[0][1]['correlation_id']
    chunks_s3_bucket = messages[0][1]['chunks_s3_bucket']
    chunks_s3_key = messages[0][1]['chunks_s3_key']
    
    logger.info(
        f"Generating embeddings for {len(messages)} chunks of document {document_id} "
        f"(correlation_id={correlation_id})"
    )
    
    try:
        # Update status to EMBEDDING
        update_document_status(document_id, 'EMBEDDING', 'embedder')
        
        # Load all chunks from S3
        response = s3_client.get_object(Bucket=chunks_s3_bucket, Key=chunks_s3_key)
        all_chunks = json.loads(response['Body'].read().decode('utf-8'))
        
        # Get chunk indices from messages
        chunk_indices = [msg['chunk_index'] for _, msg in messages]
        chunks_to_embed = [all_chunks[idx] for idx in chunk_indices]
        
        # Generate embeddings
        embeddings = generate_embeddings([chunk['text'] for chunk in chunks_to_embed])
        
        # Add embeddings to chunks
        for chunk, embedding in zip(chunks_to_embed, embeddings):
            chunk['embedding'] = embedding
        
        # Store chunks with embeddings back to S3
        embeddings_key = f"embeddings/{document_id}_batch_{min(chunk_indices)}.json"
        s3_client.put_object(
            Bucket=EMBEDDINGS_BUCKET,
            Key=embeddings_key,
            Body=json.dumps(chunks_to_embed, ensure_ascii=False).encode('utf-8'),
            ContentType='application/json',
            Metadata={
                'correlation_id': correlation_id,
                'document_id': document_id,
                'num_chunks': str(len(chunks_to_embed))
            }
        )
        
        # Calculate processing time
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Send batch to indexing queue (consolidate messages)
        indexing_message = {
            'correlation_id': correlation_id,
            'document_id': document_id,
            'embeddings_s3_bucket': EMBEDDINGS_BUCKET,
            'embeddings_s3_key': embeddings_key,
            'chunk_indices': chunk_indices,
            'metadata': messages[0][1]['metadata'],
            'stage': 'indexing',
            'previous_stage_duration_ms': duration_ms
        }
        
        sqs_client.send_message(
            QueueUrl=INDEXING_QUEUE_URL,
            MessageBody=json.dumps(indexing_message),
            MessageAttributes={
                'correlation_id': {
                    'StringValue': correlation_id,
                    'DataType': 'String'
                }
            }
        )
        
        logger.info(
            f"Generated embeddings for {len(chunks_to_embed)} chunks of document {document_id}"
        )
        
    except Exception as e:
        logger.error(f"Error generating embeddings for document {document_id}: {str(e)}")
        update_document_status(document_id, 'EMBEDDING_FAILED', 'embedder', {'error': str(e)})
        raise


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings using OpenAI API.
    
    Args:
        texts: List of text chunks
        
    Returns:
        List of embedding vectors
    """
    from openai import OpenAI
    
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    # Batch API call for efficiency
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )
    
    # Extract embeddings in order
    embeddings = [item.embedding for item in response.data]
    
    logger.info(
        f"Generated {len(embeddings)} embeddings using {EMBEDDING_MODEL} "
        f"(total tokens: {response.usage.total_tokens})"
    )
    
    return embeddings


def update_document_status(
    document_id: str,
    status: str,
    stage: str,
    additional_data: Dict[str, Any] = None
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
