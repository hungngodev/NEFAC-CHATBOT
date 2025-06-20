# general
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def retrieve_documents(query):
    pass


def create_vectorstore_filter(
    roleFilter="", contentType="", resourceType="", seen_documents=set()
):
    """
    Creates a metadata filter function for vector store retriever to make sure we don't get duplicate documents that don't match the filters

    Args:
        roleFilter (str, optional): Target audience value to match
        contentType (str, optional): Target nefac_category value to match
        resourceType (str, optional): Target resource_type value to match

    Returns:
        function: A filter function that can be used with vectorstore.as_retriever()
    """

    def filter_func(metadata):
        if metadata["title"] in seen_documents:
            return False
        else:
            seen_documents.add(metadata["title"])

        if roleFilter != "":
            if roleFilter not in metadata["audience"]:
                # print(metadata["title"],"didn't make it through due to audience")
                return False

        # Check nefac_category/contentType
        if contentType != "":
            if contentType not in metadata["nefac_category"]:
                # print(metadata["title"],"didn't make it through due to contentType")
                return False

        # Check resource_type/resourceType
        if resourceType != "":
            if resourceType not in metadata["resource_type"]:
                # print(metadata["title"],"didn't make it through due to resourceType")
                return False

        # If all specified filters pass, return True
        # print(metadata["title"],'made it through')
        return True

    return filter_func
