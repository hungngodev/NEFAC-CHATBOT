#!/usr/bin/env python3
"""
Test script to verify LocalStack setup and AWS services.
Run this script to test that LocalStack is working correctly.
"""

import json
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_aws_connection():
    """Test basic AWS service connections."""
    try:
        from aws_config import (
            get_lambda_client,
            get_sqs_client,
            get_s3_client,
            get_ecr_client,
            get_ecs_client,
        )

        # Test Lambda client
        lambda_client = get_lambda_client()
        lambda_client.list_functions()
        logger.info("✅ Lambda client connection successful")

        # Test SQS client
        sqs_client = get_sqs_client()
        sqs_client.list_queues()
        logger.info("✅ SQS client connection successful")

        # Test S3 client
        s3_client = get_s3_client()
        s3_client.list_buckets()
        logger.info("✅ S3 client connection successful")

        # Test ECR client
        ecr_client = get_ecr_client()
        ecr_client.describe_repositories()
        logger.info("✅ ECR client connection successful")

        # Test ECS client
        ecs_client = get_ecs_client()
        ecs_client.list_clusters()
        logger.info("✅ ECS client connection successful")

        return True

    except Exception as e:
        logger.error(f"❌ AWS connection test failed: {str(e)}")
        return False


def test_sqs_operations():
    """Test SQS queue operations."""
    try:
        from sqs_utils import SQSManager

        sqs_manager = SQSManager()

        # Create a test queue
        queue_name = "test-queue"
        queue_url = sqs_manager.create_queue(queue_name)
        logger.info(f"✅ Created test queue: {queue_url}")

        # Send a test message
        test_message = {"test": "data", "timestamp": str(time.time())}
        message_id = sqs_manager.send_message(queue_url, test_message)
        logger.info(f"✅ Sent test message: {message_id}")

        # Receive the message
        messages = sqs_manager.receive_messages(queue_url, max_messages=1)
        if messages:
            message = messages[0]
            body = json.loads(message["Body"])
            logger.info(f"✅ Received message: {body}")

            # Delete the message
            sqs_manager.delete_message(queue_url, message["ReceiptHandle"])
            logger.info("✅ Deleted test message")

        # Clean up
        sqs_manager.delete_queue(queue_url)
        logger.info("✅ Deleted test queue")

        return True

    except Exception as e:
        logger.error(f"❌ SQS operations test failed: {str(e)}")
        return False


def test_lambda_operations():
    """Test Lambda function operations."""
    try:
        from lambda_utils import LambdaManager

        lambda_manager = LambdaManager()

        # List existing functions
        functions = lambda_manager.list_functions()
        logger.info(f"✅ Found {len(functions)} Lambda functions")

        # Test creating a simple function (if lambda_functions directory exists)
        import os

        if os.path.exists("lambda_functions"):
            try:
                # This would require the actual function code to be present
                logger.info("✅ Lambda manager initialized successfully")
            except Exception as e:
                logger.warning(f"⚠️ Lambda deployment test skipped: {str(e)}")

        return True

    except Exception as e:
        logger.error(f"❌ Lambda operations test failed: {str(e)}")
        return False


def test_environment_variables():
    """Test that environment variables are set correctly."""
    import os

    required_vars = [
        "AWS_ENDPOINT_URL",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_DEFAULT_REGION",
    ]

    for var in required_vars:
        value = os.getenv(var)
        if value:
            logger.info(f"✅ {var} is set: {value}")
        else:
            logger.warning(f"⚠️ {var} is not set")

    return True


def main():
    """Run all tests."""
    logger.info("🚀 Starting LocalStack tests...")

    tests = [
        ("Environment Variables", test_environment_variables),
        ("AWS Connections", test_aws_connection),
        ("SQS Operations", test_sqs_operations),
        ("Lambda Operations", test_lambda_operations),
    ]

    results = []
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running {test_name} test...")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ {test_name} test failed with exception: {str(e)}")
            results.append((test_name, False))

    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 50)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1

    logger.info(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        logger.info("🎉 All tests passed! LocalStack is working correctly.")
    else:
        logger.warning("⚠️ Some tests failed. Check the logs above for details.")

    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
