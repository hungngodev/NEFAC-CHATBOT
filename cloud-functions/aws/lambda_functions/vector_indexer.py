"""
STAGE 5: Vector Indexer Lambda
Triggered by indexing_queue (batched). Uploads chunks+embeddings to Qdrant and Elasticsearch.
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
GRAPH_QUEUE_URL = os.environ.get('GRAPH_QUEUE_URL')
COMPLETION_QUEUE_URL = os.environ['COMPLETION_QUEUE_URL']
TRACKING_TABLE_NAME = os.environ.get('TRACKING_TABLE_NAME', 'nefac-document-tracking')
QDRANT_ENABLE = os.environ.get('QDRANT_ENABLE', 'true').lower() == 'true'
ES_ENABLE = os.environ.get('ES_ENABLE', 'false').lower() == 'true'
GRAPH_ENABLE = os.environ.get('GRAPH_ENABLE', 'false').lower() == 'true'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Index chunks+embeddings to vector stores from SQS messages (batched).
    
    Args:
        event: SQS event with embedding references (batched 10-20 messages)
        context: Lambda context
        
    Returns:
        Batch response for SQS
    """
    start_time = time.time()
    batch_item_failures = []
    
    # Group messages by document_id
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
            process_document_indexing(doc_id, messages, start_time)
        except Exception as e:
            logger.error(f"Error indexing document {doc_id}: {str(e)}", exc_info=True)
            for record, _ in messages:
                batch_item_failures.append({"itemIdentifier": record['messageId']})
    
    return {
        "batchItemFailures": batch_item_failures
    }


def process_document_indexing(
    document_id: str,
    messages: List[tuple],
    start_time: float
) -> None:
    """Process indexing for a single document."""
    correlation_id = messages[0][1]['correlation_id']
    
    logger.info(
        f"Indexing {len(messages)} batches for document {document_id} "
        f"(correlation_id={correlation_id})"
    )
    
    try:
        # Update status to INDEXING
        update_document_status(document_id, 'INDEXING', 'indexer')
        
        # Collect all chunks with embeddings
        all_chunks = []
        for _, message_body in messages:
            embeddings_s3_bucket = message_body['embeddings_s3_bucket']
            embeddings_s3_key = message_body['embeddings_s3_key']
            
            # Load chunks with embeddings
            response = s3_client.get_object(Bucket=embeddings_s3_bucket, Key=embeddings_s3_key)
            chunks = json.loads(response['Body'].read().decode('utf-8'))
            all_chunks.extend(chunks)
        
        # Index to vector stores
        if QDRANT_ENABLE:
            index_to_qdrant(all_chunks, correlation_id)
        
        if ES_ENABLE:
            index_to_elasticsearch(all_chunks, correlation_id)
        
        # Calculate processing time
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Determine next queue
        next_queue_url = GRAPH_QUEUE_URL if GRAPH_ENABLE else COMPLETION_QUEUE_URL
        next_stage = 'graph' if GRAPH_ENABLE else 'completion'
        
        # Send to next queue (single message per document)
        next_message = {
            'correlation_id': correlation_id,
            'document_id': document_id,
            'num_chunks_indexed': len(all_chunks),
            'metadata': messages[0][1]['metadata'],
            'stage': next_stage,
            'previous_stage_duration_ms': duration_ms
        }
        
        sqs_client.send_message(
            QueueUrl=next_queue_url,
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
            'INDEXED',
            'indexer',
            {
                'num_chunks_indexed': len(all_chunks),
                'duration_ms': duration_ms,
                'qdrant_enabled': QDRANT_ENABLE,
                'elasticsearch_enabled': ES_ENABLE
            }
        )
        
        logger.info(f"Indexed {len(all_chunks)} chunks for document {document_id}")
        
    except Exception as e:
        logger.error(f"Error indexing document {document_id}: {str(e)}")
        update_document_status(document_id, 'INDEXING_FAILED', 'indexer', {'error': str(e)})
        raise


def index_to_qdrant(chunks: List[Dict[str, Any]], correlation_id: str) -> None:
    """Index chunks to Qdrant with hybrid search."""
    from llama_index.core.schema import TextNode
    from llama_index.vector_stores.qdrant import QdrantVectorStore
    from llama_index.core import VectorStoreIndex, StorageContext
    
    qdrant_url = os.environ['QDRANT_ENDPOINT']
    collection_name = os.environ['QDRANT_CLUSTER_ID']
    api_key = os.environ.get('QDRANT_API_KEY')
    enable_hybrid = os.environ.get('QDRANT_ENABLE_HYBRID', 'false').lower() == 'true'
    
    vector_store = QdrantVectorStore(
        collection_name=collection_name,
        url=qdrant_url,
        api_key=api_key,
        enable_hybrid=enable_hybrid,
        fastembed_sparse_model="Qdrant/bm25" if enable_hybrid else None,
    )
    
    # Convert chunks to TextNodes
    nodes = []
    for chunk in chunks:
        node = TextNode(
            text=chunk['text'],
            metadata=chunk['metadata'],
            id_=chunk['id'],
            embedding=chunk.get('embedding')
        )
        nodes.append(node)
    
    # Create index (this uploads to Qdrant)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex(nodes=nodes, storage_context=storage_context)
    
    logger.info(f"Indexed {len(nodes)} nodes to Qdrant (hybrid={enable_hybrid})")


def index_to_elasticsearch(chunks: List[Dict[str, Any]], correlation_id: str) -> None:
    """Index chunks to Elasticsearch."""
    from llama_index.core.schema import TextNode
    from llama_index.vector_stores.elasticsearch import ElasticsearchStore
    from llama_index.core import VectorStoreIndex, StorageContext
    
    es_url = os.environ['ES_HOST']
    index_name = os.environ['ES_INDEX']
    
    store = ElasticsearchStore(index_name=index_name, es_url=es_url)
    
    # Convert chunks to TextNodes
    nodes = []
    for chunk in chunks:
        node = TextNode(
            text=chunk['text'],
            metadata=chunk['metadata'],
            id_=chunk['id'],
            embedding=chunk.get('embedding')
        )
        nodes.append(node)
    
    # Create index (this uploads to Elasticsearch)
    storage_context = StorageContext.from_defaults(vector_store=store)
    VectorStoreIndex(nodes=nodes, storage_context=storage_context)
    
    logger.info(f"Indexed {len(nodes)} nodes to Elasticsearch")


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
