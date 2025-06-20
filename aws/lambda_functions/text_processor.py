import json
import logging
from typing import Dict, List, Any
import spacy
import numpy as np
from sklearn.decomposition import PCA

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Load spaCy model (you'll need to include this in your Lambda layer)
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # Fallback if model not available
    nlp = None
    logger.warning("spaCy model not available, using basic text processing")

def create_equal_sized_chunks(text: str, chunk_size: int = 1000) -> List[str]:
    """
    Create equal-sized chunks using spaCy for intelligent sentence boundaries.
    
    Args:
        text: Input text to chunk
        chunk_size: Target size for each chunk (in characters)
    
    Returns:
        List of text chunks
    """
    if nlp is None:
        # Basic chunking without spaCy
        return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    
    # Process text with spaCy
    doc = nlp(text)
    chunks = []
    current_chunk = ""
    
    for sent in doc.sents:
        sent_text = sent.text.strip()
        if len(current_chunk) + len(sent_text) <= chunk_size:
            current_chunk += " " + sent_text if current_chunk else sent_text
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sent_text
    
    # Add the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def transform_to_embeddings(text_chunks: List[str]) -> List[List[float]]:
    """
    Transform text chunks to embeddings using Llama or a similar model.
    This is a placeholder - you'll need to implement the actual embedding logic.
    
    Args:
        text_chunks: List of text chunks
    
    Returns:
        List of embedding vectors
    """
    # Placeholder implementation
    # In production, you would use your Llama model here
    embeddings = []
    for chunk in text_chunks:
        # Simple hash-based embedding for demonstration
        # Replace with actual Llama embedding logic
        embedding = [hash(chunk) % 1000 for _ in range(768)]  # 768-dim embedding
        embeddings.append(embedding)
    
    return embeddings

def apply_pca(embeddings: List[List[float]], n_components: int = 256) -> List[List[float]]:
    """
    Apply PCA to reduce embedding dimensions.
    
    Args:
        embeddings: List of embedding vectors
        n_components: Number of components to keep
    
    Returns:
        List of reduced-dimension embeddings
    """
    if len(embeddings) == 0:
        return []
    
    # Convert to numpy array
    embeddings_array = np.array(embeddings)
    
    # Apply PCA
    pca = PCA(n_components=min(n_components, embeddings_array.shape[1]))
    reduced_embeddings = pca.fit_transform(embeddings_array)
    
    return reduced_embeddings.tolist()

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function handler for text processing pipeline.
    
    Expected event format:
    {
        "text": "Input text to process",
        "chunk_size": 1000,
        "pca_components": 256
    }
    """
    try:
        # Extract parameters from event
        text = event.get('text', '')
        chunk_size = event.get('chunk_size', 1000)
        pca_components = event.get('pca_components', 256)
        
        if not text:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No text provided'})
            }
        
        logger.info(f"Processing text of length {len(text)}")
        
        # Step 1: Create equal-sized chunks
        chunks = create_equal_sized_chunks(text, chunk_size)
        logger.info(f"Created {len(chunks)} chunks")
        
        # Step 2: Transform to embeddings
        embeddings = transform_to_embeddings(chunks)
        logger.info(f"Generated {len(embeddings)} embeddings")
        
        # Step 3: Apply PCA
        reduced_embeddings = apply_pca(embeddings, pca_components)
        logger.info(f"Reduced embeddings to {pca_components} dimensions")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'chunks': chunks,
                'embeddings': reduced_embeddings,
                'chunk_count': len(chunks),
                'embedding_dimensions': len(reduced_embeddings[0]) if reduced_embeddings else 0
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing text: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        } 