import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    

    return {
        "Status": 200,
        "Body": "Hello World"
    }