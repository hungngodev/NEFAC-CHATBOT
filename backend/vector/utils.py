# general
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def retrieve_documents(query):
    pass
def create_vectorstore_filter(roleFilter=None, contentType=None, resourceType=None):
    """
    Creates a metadata filter function for vector store retriever that checks if single target values
    exist in corresponding metadata arrays.
    
    Args:
        roleFilter (str, optional): Target audience value to match
        contentType (str, optional): Target nefac_category value to match
        resourceType (str, optional): Target resource_type value to match
        
    Returns:
        function: A filter function that can be used with vectorstore.as_retriever()
    """
    def filter_func(metadata):
        # Check audience/roleFilter
        if roleFilter is not None:
            if roleFilter not in metadata['audience']:
                return False

        # Check nefac_category/contentType
        if contentType is not None:
            if contentType not in metadata['nefac_category']:
                return False

        # Check resource_type/resourceType
        if resourceType is not None:
            if resourceType not in metadata['resource_type']:
                return False

        # If all specified filters pass, return True
        return True

    return filter_func
