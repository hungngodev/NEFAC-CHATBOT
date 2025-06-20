import json
import logging
import datetime
from typing import Dict, List, Any, Optional
from .aws_config import get_sqs_client

logger = logging.getLogger(__name__)


class SQSManager:
    """Utility class for managing SQS queues and messages."""

    def __init__(self):
        self.sqs_client = get_sqs_client()

    def create_queue(
        self, queue_name: str, attributes: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Create an SQS queue.

        Args:
            queue_name: Name of the queue
            attributes: Optional queue attributes

        Returns:
            Queue URL
        """
        try:
            if attributes is None:
                attributes = {
                    "VisibilityTimeout": "30",
                    "MessageRetentionPeriod": "1209600",  # 14 days
                    "ReceiveMessageWaitTimeSeconds": "20",  # Long polling
                }

            response = self.sqs_client.create_queue(
                QueueName=queue_name, Attributes=attributes
            )

            queue_url = response["QueueUrl"]
            logger.info(f"Created queue: {queue_name} -> {queue_url}")
            return queue_url

        except Exception as e:
            logger.error(f"Error creating queue {queue_name}: {str(e)}")
            raise

    def delete_queue(self, queue_url: str) -> bool:
        """
        Delete an SQS queue.

        Args:
            queue_url: URL of the queue to delete

        Returns:
            True if successful
        """
        try:
            self.sqs_client.delete_queue(QueueUrl=queue_url)
            logger.info(f"Deleted queue: {queue_url}")
            return True
        except Exception as e:
            logger.error(f"Error deleting queue {queue_url}: {str(e)}")
            return False

    def send_message(
        self, queue_url: str, message_body: Dict[str, Any], delay_seconds: int = 0
    ) -> str:
        """
        Send a message to an SQS queue.

        Args:
            queue_url: URL of the queue
            message_body: Message body as dictionary
            delay_seconds: Delay before message is visible

        Returns:
            Message ID
        """
        try:
            response = self.sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message_body),
                DelaySeconds=delay_seconds,
            )

            message_id = response["MessageId"]
            logger.info(f"Sent message {message_id} to queue {queue_url}")
            return message_id

        except Exception as e:
            logger.error(f"Error sending message to {queue_url}: {str(e)}")
            raise

    def receive_messages(
        self, queue_url: str, max_messages: int = 10, wait_time: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Receive messages from an SQS queue.

        Args:
            queue_url: URL of the queue
            max_messages: Maximum number of messages to receive
            wait_time: Long polling wait time

        Returns:
            List of message dictionaries
        """
        try:
            response = self.sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time,
                AttributeNames=["All"],
                MessageAttributeNames=["All"],
            )

            messages = response.get("Messages", [])
            logger.info(f"Received {len(messages)} messages from {queue_url}")
            return messages

        except Exception as e:
            logger.error(f"Error receiving messages from {queue_url}: {str(e)}")
            return []

    def delete_message(self, queue_url: str, receipt_handle: str) -> bool:
        """
        Delete a message from an SQS queue.

        Args:
            queue_url: URL of the queue
            receipt_handle: Receipt handle of the message

        Returns:
            True if successful
        """
        try:
            self.sqs_client.delete_message(
                QueueUrl=queue_url, ReceiptHandle=receipt_handle
            )
            logger.info(f"Deleted message with receipt handle: {receipt_handle}")
            return True
        except Exception as e:
            logger.error(f"Error deleting message: {str(e)}")
            return False

    def get_queue_attributes(self, queue_url: str) -> Dict[str, str]:
        """
        Get attributes of an SQS queue.

        Args:
            queue_url: URL of the queue

        Returns:
            Dictionary of queue attributes
        """
        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=queue_url, AttributeNames=["All"]
            )
            return response.get("Attributes", {})
        except Exception as e:
            logger.error(f"Error getting queue attributes: {str(e)}")
            return {}


# Example usage for text processing pipeline
def setup_text_processing_queues() -> Dict[str, str]:
    """
    Set up SQS queues for the text processing pipeline.

    Returns:
        Dictionary mapping queue names to URLs
    """
    sqs_manager = SQSManager()
    queues = {}

    # Queue for incoming text processing requests
    queues["text_processing_input"] = sqs_manager.create_queue(
        "text-processing-input",
        attributes={
            "VisibilityTimeout": "300",  # 5 minutes for processing
            "MessageRetentionPeriod": "1209600",
            "ReceiveMessageWaitTimeSeconds": "20",
        },
    )

    # Queue for processed chunks
    queues["processed_chunks"] = sqs_manager.create_queue(
        "processed-chunks",
        attributes={
            "VisibilityTimeout": "60",
            "MessageRetentionPeriod": "1209600",
            "ReceiveMessageWaitTimeSeconds": "20",
        },
    )

    # Queue for embedding results
    queues["embedding_results"] = sqs_manager.create_queue(
        "embedding-results",
        attributes={
            "VisibilityTimeout": "60",
            "MessageRetentionPeriod": "1209600",
            "ReceiveMessageWaitTimeSeconds": "20",
        },
    )

    logger.info(f"Set up {len(queues)} queues for text processing pipeline")
    return queues


def send_text_processing_request(
    text: str, chunk_size: int = 1000, pca_components: int = 256
) -> str:
    """
    Send a text processing request to the SQS queue.

    Args:
        text: Text to process
        chunk_size: Size of chunks to create
        pca_components: Number of PCA components

    Returns:
        Message ID
    """
    sqs_manager = SQSManager()

    # Get queue URL (you might want to store this in environment variables)
    queue_url = sqs_manager.create_queue("text-processing-input")

    message_body = {
        "text": text,
        "chunk_size": chunk_size,
        "pca_components": pca_components,
        "timestamp": str(datetime.datetime.now()),
    }

    return sqs_manager.send_message(queue_url, message_body)
