"""
STAGE 3: Semantic Chunker Lambda
Triggered by chunking_queue. Applies SemanticDoubleMergingSplitterNodeParser.
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
EMBEDDING_QUEUE_URL = os.environ['EMBEDDING_QUEUE_URL']
TRACKING_TABLE_NAME = os.environ.get('TRACKING_TABLE_NAME', 'nefac-document-tracking')
CHUNKS_BUCKET = os.environ['CHUNKS_BUCKET']

# LlamaIndex imports (lazy loaded)
_semantic_splitter = None


def get_semantic_splitter():
    """Lazy load semantic splitter to avoid cold start overhead."""
    global _semantic_splitter
    if _semantic_splitter is None:
        from llama_index.core.node_parser import (
            LanguageConfig,
            SemanticDoubleMergingSplitterNodeParser,
            SimpleNodeParser,
        )
        
        language = os.getenv("SEMANTIC_SPLITTER_LANGUAGE", "english")
        spacy_model = os.getenv("SEMANTIC_SPLITTER_SPACY_MODEL", "en_core_web_sm")
        
        try:
            config = LanguageConfig(language=language, spacy_model=spacy_model)
            _semantic_splitter = SemanticDoubleMergingSplitterNodeParser(
                language_config=config,
                initial_threshold=float(os.getenv("SEMANTIC_SPLITTER_INITIAL_THRESHOLD", "0.4")),
                appending_threshold=float(os.getenv("SEMANTIC_SPLITTER_APPEND_THRESHOLD", "0.5")),
                merging_threshold=float(os.getenv("SEMANTIC_SPLITTER_MERGE_THRESHOLD", "0.5")),
                max_chunk_size=int(os.getenv("SEMANTIC_SPLITTER_MAX_CHUNK", "2000")),
            )
            logger.info(f"Initialized SemanticDoubleMergingSplitterNodeParser (model={spacy_model})")
        except Exception as e:
            logger.warning(f"Semantic splitter unavailable: {e}. Using SimpleNodeParser.")
            _semantic_splitter = SimpleNodeParser.from_defaults(chunk_size=2000)
    
    return _semantic_splitter


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Chunk documents from SQS messages.
    
    Args:
        event: SQS event with parsed document references
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
            batch_item_failures.append({"itemIdentifier": record['messageId']})
    
    return {
        "batchItemFailures": batch_item_failures
    }


def process_message(record: Dict[str, Any], start_time: float) -> None:
    """Process a single SQS message."""
    message_body = json.loads(record['body'])
    correlation_id = message_body['correlation_id']
    document_id = message_body['document_id']
    parsed_s3_bucket = message_body['parsed_s3_bucket']
    parsed_s3_key = message_body['parsed_s3_key']
    
    logger.info(f"Chunking document: {document_id} (correlation_id={correlation_id})")
    
    try:
        # Update status to CHUNKING
        update_document_status(document_id, 'CHUNKING', 'chunker')
        
        # Download parsed text from S3
        response = s3_client.get_object(Bucket=parsed_s3_bucket, Key=parsed_s3_key)
        parsed_text = response['Body'].read().decode('utf-8')
        
        # Apply semantic chunking
        chunks = chunk_text(parsed_text, message_body['metadata'])
        
        if not chunks:
            raise ValueError("Chunking resulted in no chunks")
        
        # Store chunks in S3
        chunks_key = f"chunks/{document_id}.json"
        s3_client.put_object(
            Bucket=CHUNKS_BUCKET,
            Key=chunks_key,
            Body=json.dumps(chunks, ensure_ascii=False).encode('utf-8'),
            ContentType='application/json',
            Metadata={
                'correlation_id': correlation_id,
                'document_id': document_id,
                'num_chunks': str(len(chunks))
            }
        )
        
        # Calculate processing time
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Send each chunk to embedding queue (fan-out)
        for idx, chunk in enumerate(chunks):
            chunk_message = {
                'correlation_id': correlation_id,
                'document_id': document_id,
                'chunk_index': idx,
                'total_chunks': len(chunks),
                'chunk_id': chunk['id'],
                'chunks_s3_bucket': CHUNKS_BUCKET,
                'chunks_s3_key': chunks_key,
                'metadata': message_body['metadata'],
                'stage': 'embedding',
                'previous_stage_duration_ms': duration_ms
            }
            
            sqs_client.send_message(
                QueueUrl=EMBEDDING_QUEUE_URL,
                MessageBody=json.dumps(chunk_message),
                MessageAttributes={
                    'correlation_id': {
                        'StringValue': correlation_id,
                        'DataType': 'String'
                    },
                    'chunk_index': {
                        'StringValue': str(idx),
                        'DataType': 'Number'
                    }
                }
            )
        
        # Update status
        update_document_status(
            document_id,
            'CHUNKED',
            'chunker',
            {
                'num_chunks': len(chunks),
                'duration_ms': duration_ms
            }
        )
        
        logger.info(f"Document {document_id} chunked into {len(chunks)} chunks")
        
    except Exception as e:
        logger.error(f"Error chunking document {document_id}: {str(e)}")
        update_document_status(document_id, 'CHUNK_FAILED', 'chunker', {'error': str(e)})
        raise


def chunk_text(text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Apply semantic chunking to text.
    
    Args:
        text: Parsed text content
        metadata: Document metadata
        
    Returns:
        List of chunk dictionaries
    """
    from llama_index.core import Document as LIDocument
    
    splitter = get_semantic_splitter()
    li_doc = LIDocument(text=text, metadata=metadata)
    nodes = splitter.get_nodes_from_documents([li_doc])
    
    chunks = []
    for idx, node in enumerate(nodes):
        chunks.append({
            'id': f"{metadata.get('filename', 'doc')}:chunk:{idx}",
            'text': node.get_content(),
            'metadata': {
                **metadata,
                'chunk_index': idx,
                'total_chunks': len(nodes),
                'node_id': node.node_id
            }
        })
    
    return chunks


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
