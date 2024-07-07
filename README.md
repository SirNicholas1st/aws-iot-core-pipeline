# aws-iot-core-pipeline WIP

# Summary

The goal is to make explore AWS iot-core and Kinesis Firehose services. 

The preliminary pipeline plan is the following:
1. Receiver would be AWS iotcore, client authentication with certificate, data received via MQTT
2. Kinesis Firehose aggregates the messages for example to 1 minute batches. The raw data would also need to be stored in a s3
3. Lambda handles the aggregated batches and stores the parsed data to a s3 bucket.

# Prerequisites

1. AWS Account
2. AWS CLI https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
3. AWS CLI configured with an IAM role with generous priviledges.
4. AWS SAM https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html

# Getting started

1. Create an empty directory
2. Run ```sam init``` in the directory. Follow the steps, this will create alot of boilerplate resources. I added most of these to .gitignore to not clutter this repo so that the meaningfull content can be found more easily.
3. Run ```sam build```. NOTE: SAM will create a new directory.
4. Quick and dirty, run ```sam deploy --guided```. This is a guided deployment. In the future I will add a deployment script.