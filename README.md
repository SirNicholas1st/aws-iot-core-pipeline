# aws-iot-core-pipeline WIP

# Summary

The goal is to explore AWS iot-core and Kinesis Firehose services. 

The preliminary pipeline plan is the following:
1. Receiver would be AWS iotcore, client authentication with certificate, data received via MQTT
2. Kinesis Firehose aggregates the messages for example to 1 minute batches. The raw data would also need to be stored in a s3
3. Lambda handles the aggregated batches and stores the parsed data to a s3 bucket.

The directory "iot-core-pipeline" will have all the stack related files and code while the directory "Various" will have some testing scripts etc.

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

# IoT thing setup

Handling certificates in the CloudFormation template seems to be a real pain, and you still need to do some manual work outside of the template. This is why I opted to do some Click-Ops for the certificate part. 

Also it maybe would be best if the certificates are created outside of the CF-template, since if we need to for example create new ones, we would need to modify the template. In this case I think Click-Ops would be the way to go.

## CF setup

In the CF-Template I first defined the thing to be created as follows

```
  IoTThing:
    Type: AWS::IoT::Thing
    DeletionPolicy: Delete
    UpdateReplacePolicy: Delete
    Properties:
         ThingName: !Sub '${Environment}-iot-thing-321'
```
I wanted to delete the thing if I delete the stack. Thats why it has the delete and update policies.

Then I defined a IAM-policy that allows to connect and publish to the specified topic and all topics under it. If you would for example have multiple customers use the same thing, then I would most likely for example create topic specific policies + multiple certs. 

```
IoTPolicy:
    Type: AWS::IoT::Policy
    Properties:
         PolicyName: 'IotPolicy'
         PolicyDocument:
              Version: '2012-10-17'
              Statement:
                - Effect: 'Allow'
                  Action:
                    - 'iot:Connect'
                    - 'iot:Publish'
                  Resource: 
                    - !Sub 'arn:aws:iot:${AWS::Region}:${AWS::AccountId}:client/${Environment}-iot-thing-321'
                      # Allow publishing to a specific topic.
                    - !Sub 'arn:aws:iot:${AWS::Region}:${AWS::AccountId}:topic/${IotTopicName}'
                      # Allow publishing to any sub-topics under the specific topic.
                    - !Sub 'arn:aws:iot:${AWS::Region}:${AWS::AccountId}:topic/${IotTopicName}/*'
```
Now when the stack is deployed, we will have the thing and the IAM-policy, these both are needed for the certificate config.

## Certificate setup from console

1. Navigate to IoT-core in the AWS Console
2. From the Left navigation bar go to All Devices --> Things
3. Choose the created thing.
4. Choose Certificates and Click "Create certificate"
5. Download all the stuff, store it securely.
6. Click the created certificate
7. You will see that it has no policies attached, attach the created policy to it.
8. Remember to activate it.

## Testing the Thing

1. I created a simple publisher notebook, which can be found under the directory "Various"
2. Fill in the required parameters. NOTE: The client-id needs to match the thing name + the topic has to be one that the IAM-policy allows the publishing. The endpoint cant be found from under the "Settings" in the AWS IoT Core.
3. Go to AWS IoT Core and subscribe to the topic with MQTT-test client.
4. Send messages with the notebook.
5. View the messages:
![message-sample](Pics/iot-core-hello.png)


### Messages wont appear what to do

Review all the variables in the sending script, if the script does not give you any errors do the following:

1. From the left navigation bar go to "Thing" and choose the thing.
2. Click "Activity" and try to send a message.
3. Check that the activities show a connected event, this is good and it means we can connect okay.
4. If you get a immidiate disconnect due to "CLIENT ERROR" it most likely is due that the IAM-policy does not have the required priviledges to publish to the topic you are trying to send.
5. Review the topic that you are tring to send messages and use the wildcard '#' in the test client.

If you cannot connect check that the certificate is active and it is attached to the IAM-policy.


# Firehose Delivery Setup to S3

First I defined the the stream itself:

```
FirehoseDeliveryStream:
    Type: AWS::KinesisFirehose::DeliveryStream
    DependsOn:
         - FirehoseRole
    Properties:
        DeliveryStreamName: !Sub ${Environment}-firehose-delivery-stream-321
        DeliveryStreamType: DirectPut
        S3DestinationConfiguration:
            BucketARN: !GetAtt RawDataBucket.Arn
            RoleARN: !GetAtt FirehoseRole.Arn
            BufferingHints:
                 IntervalInSeconds: 60
                 SizeInMBs: 1
            CompressionFormat: GZIP
            Prefix: !Sub '${Environment}/data/'
            ErrorOutputPrefix: !Sub '${Environment}/error/'
            CloudWatchLoggingOptions:
                Enabled: true
                LogGroupName: !Sub "/aws/kinesisfirehose/${Environment}-firehose-321"
                LogStreamName: "S3DeliveryFromIoTCore"
```
The stream is configured to buffer the received data for 60 seconds or 1MB, whichever comes first. After the buffering is done the file will be stored to the defined s3 bucket, in this case the raw data bucket. The data amount I'm sending is so low, that this buffer is sufficent.

Then I needed to give the stream some rights, namely to put objects to the s3 bucket and logging related permissions. I created the role as follows:

```
  FirehoseRole:
    Type: AWS::IAM::Role
    Properties:
        AssumeRolePolicyDocument:
          Version: "2012-10-17"
          Statement:
            - Effect: Allow
              Principal:
                Service: "firehose.amazonaws.com"
              Action: "sts:AssumeRole"
        Policies:
          - PolicyName: !Sub '${Environment}-firehoserole-321'
            PolicyDocument: 
              Statement:
                - Effect: Allow
                  Action:
                    - s3:PutObject
                    - s3:GetBucketLocation
                    - s3:ListBucket
                  Resource:
                    - !Sub arn:aws:s3:::${Environment}-${RawBucketName}/
                    - !Sub arn:aws:s3:::${Environment}-${RawBucketName}/*
                - Effect: Allow
                  Action:
                    - logs:CreateLogGroup
                    - logs:CreateLogStream
                    - logs:PutLogEvents
                  Resource: '*'
```
As we have attached the created role to the stream it has the permissions we have defined for the role.

But we are not done with the permissions yet, now we need to create a role that the IoT rule will use, it needs the permissions to put records to the delivery stream:

```
  IotRoleFirehose:
    Type: AWS::IAM::Role
    Properties:
        AssumeRolePolicyDocument:
          Version: "2012-10-17"
          Statement:
            - Effect: Allow
              Principal:
                Service: "iot.amazonaws.com"
              Action: "sts:AssumeRole"
        Policies:
          - PolicyName: !Sub '${Environment}-iot-to-firehose-policy'
            PolicyDocument: 
              Version: "2012-10-17"
              Statement:
                - Effect: Allow
                  Action:
                    - firehose:PutRecord
                    - firehose:PutRecordBatch
                  Resource: !Sub arn:aws:firehose:${AWS::Region}:${AWS::AccountId}:deliverystream/${Environment}-firehose-delivery-stream-321
```

Finally we can define a topic rule for the received messages:

```
  IoTRuleTopic:
    Type: AWS::IoT::TopicRule
    Properties:
      RuleName: !Sub '${Environment}iotrule321'
      TopicRulePayload:
        Actions:
          - Firehose:
              DeliveryStreamName: !Ref FirehoseDeliveryStream
              RoleArn: !GetAtt IotRoleFirehose.Arn
              Separator: "\n"
        AwsIotSqlVersion: "2016-03-23"
        Sql: !Sub SELECT topic() as topic, * FROM '${IotTopicName}/+'
        RuleDisabled: False
```
In this rule we define the sql on how we wish to take the data and the destination for the data. I'm including the topic in the data, this could be beneficial if for example we have a customer that sends data to the topic but we use sub topics for example to differintiate between equipment and we would like to parse the data while keeping the equipment data.

The buffered files in the s3 will now look like the following:
```
{"topic":"iot-test-topic/asdasd","message":"Hello, world!"}
{"topic":"iot-test-topic/asdasd","message":"Hello, world!"}
{"topic":"iot-test-topic/asdasd","message":"Hello, world!"}
{"topic":"iot-test-topic/asdasd","message":"Hello, world!"}
{"topic":"iot-test-topic/asdasd","message":"Hello, world!"}
{"topic":"iot-test-topic/asdasd","message":"Hello, world!"}
```

# Triggering Lambda from the delivery stream

The first thing I did is that I modifed the Firehose resource to the following:

```
FirehoseDeliveryStream:
    Type: AWS::KinesisFirehose::DeliveryStream
    DependsOn:
         - FirehoseRole
         - ParserLambda
    Properties:
        DeliveryStreamName: !Sub ${Environment}-firehose-delivery-stream-321
        DeliveryStreamType: DirectPut
        ExtendedS3DestinationConfiguration:
            BucketARN: !GetAtt TargetBucket.Arn
            RoleARN: !GetAtt FirehoseRole.Arn
            BufferingHints:
                 IntervalInSeconds: 60
                 SizeInMBs: 1
            CompressionFormat: GZIP
            FileExtension: .csv.gz
            Prefix: !Sub '${Environment}/data/'
            ErrorOutputPrefix: !Sub '${Environment}/error/'
            CloudWatchLoggingOptions:
                Enabled: true
                LogGroupName: !Sub "/aws/kinesisfirehose/${Environment}-firehose-321"
                LogStreamName: "S3DeliveryFromIoTCore"
            ProcessingConfiguration:
                Enabled: True
                Processors:
                  - Type: Lambda
                    Parameters:
                      - ParameterName: LambdaArn
                        ParameterValue: !GetAtt ParserLambda.Arn
            S3BackupMode: "Enabled"
            S3BackupConfiguration:
                  BucketARN: !GetAtt RawDataBucket.Arn
                  RoleARN: !GetAtt FirehoseRole.Arn
                  Prefix: !Sub '${Environment}/data/'
                  CompressionFormat: GZIP
                  BufferingHints:
                       IntervalInSeconds: 60
                       SizeInMBs: 1
```

The major changes done to this resources is that instead of ```S3DestinationConfiguration``` we use ```ExtendedS3DestinationConfiguration``` which gives us more options. We added a processing configuration pointing to the intended Lambda, this means that the Lambda function we define will be triggered by the batches created by the stream. Lastly I added a back up config and set it to "Enabled" this means that the stream will save the raw batches to the configured S3 bucket on top of triggering the Lambda. Also I needed to add the permissions for the stream role to invoke the Lambda.

Lastly I created the Lambda and gave it the needed permissions to fetch data from the stream. For the Lambda we do not define any triggers, it is completely handled by us placing it as the processor to the delivery stream.

# Lambda

The Lambda itself is pretty basic, I have not included the parsing part since it differs for every use case. There is some Delivery Stream "specific" magic tho that I will explain.

The even that the Delivery Stream pushes to the Lambda looks like the following:

```
{
    "invocationId": "08ef5d48-b830-41f6-b5c6-087bec91a044",
    "deliveryStreamArn": "arn:aws:firehose:eu-west-1:<accountid>:deliverystream/sirnicholas-firehose-delivery-stream-321",
    "region": "eu-west-1",
    "records": [
        {
            "recordId": "49653879352194574551977745507220068608511091278050492418000000",
            "approximateArrivalTimestamp": 1720859923841,
            "data": "eyJ0b3BpYyI6ImlvdC10ZXN0LXRvcGljL2FzZGFzZCIsIm1lc3NhZ2UiOiJIZWxsbywgd29ybGQhIn0K"
        },
        {
            "recordId": "49653879352194574551977745507221277534330706044664152066000000",
            "approximateArrivalTimestamp": 1720859926070,
            "data": "eyJ0b3BpYyI6ImlvdC10ZXN0LXRvcGljL2FzZGFzZCIsIm1lc3NhZ2UiOiJIZWxsbywgd29ybGQhIn0K"
        },
        {
            "recordId": "49653879352194574551977745507222486460150320811277811714000000",
            "approximateArrivalTimestamp": 1720859927903,
            "data": "eyJ0b3BpYyI6ImlvdC10ZXN0LXRvcGljL2FzZGFzZCIsIm1lc3NhZ2UiOiJIZWxsbywgd29ybGQhIn0K"
        },
        {
            "recordId": "49653879352194574551977745507223695385969935509171994626000000",
            "approximateArrivalTimestamp": 1720859929724,
            "data": "eyJ0b3BpYyI6ImlvdC10ZXN0LXRvcGljL2FzZGFzZCIsIm1lc3NhZ2UiOiJIZWxsbywgd29ybGQhIn0K"
        }
    ]
}
```
One event will consist of multiple records. The records are the data that we are interested in, namely the "data" part. Also the "recordId" is used in the Lambdas return statement.

The data itself is base64 encoded so we need to first decode it. I Chose the following approach (based on https://docs.aws.amazon.com/lambda/latest/dg/with-kinesis-example.html):

```
def decode_stream_batch(event: str) -> dict:

    decoded_records = []
    # keeping the originals for the return response
    original_records = []

    records = event["records"]

    for record in records:
        decoded_data = base64.b64decode(record["data"]).decode("utf-8")

        json_data = json.loads(decoded_data)

        decoded_records.append(json_data)
        original_records.append(record)

    return {
        "original_records": original_records,
        "decoded_records": decoded_records
    }
```

The function will loop thru records in the record section of the event and store the original records and the decoded data from the data key to their own lists. Finally it returns a dictionary so we can access the original data and the decoded data with keys. 

The original data is kept so we can return it as a response from the Lambda, this way the Delivery Stream knows that the parsing of the records have been successful and it wont store them under errors. If the response is not correct the batch will be stored under errors even in the case where the Lambda runs successfully.

## What to return from the Lambda?

The stream needs to know that the processing has been successful or not and for that it needs a response like the following for every record:

```
{
    "recordId": "<recordId from the Lambda input>",
    "result": "Ok",
    "data": "<Base64 encoded Transformed data>"
}
```

The way I handled this is that I created the following function to prepare the response (docs: https://docs.aws.amazon.com/firehose/latest/dev/data-transformation.html):
```
def prepare_response(original_records: dict) -> str:

    response = {
        "records": [
            {
            "recordId": record["recordId"],
            "result": "Dropped",
            "data": record["data"]
            } for record in original_records
        ]
    }

    return response
```

The function takes original records' data, namely the recordId and the base64 encoded original data and creates a response for all the processed records. The reason here for the result: Dropped is that if its "Ok", it will essentially save the raw data to the target bucket. Since the Lambda itself saves the data I do not want the Lambda to send data back to stream for saving purposes.

In the correct way of using the parsing from the stream the data should have the data after the parsing. In this case the Lambda would send the data back to the stream and the stream would save it to the defined s3 bucket (for records with status "Ok").

It should be noted, since this is a testing Lambda it does not have error handling or sufficent logging. For commercial use those atleast should be implemented, but as for barebones starting point the Lambda is sufficent.


# Why I do not like this setup & improvement ideas

WIP