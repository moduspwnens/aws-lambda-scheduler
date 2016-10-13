from __future__ import print_function

import json, datetime, time
import boto3, botocore

datetime_string_format = "%Y-%m-%dT%H:%M:%SZ"

class LambdaHandler(object):

    def __init__(self, context):
        pass

    def handle_event(self, unvalidated_event, context):
        print("Received event: {}".format(json.dumps(unvalidated_event)))
        
        if "warming" in unvalidated_event:
            return {
                "message": "Function warmed successfully."
            }
        
        if not hasattr(self, "s3_bucket"):
            self.s3_bucket = boto3.resource("s3").Bucket(self.get_s3_bucket_name())
        
        event = self.validate_event(unvalidated_event)

        print("Validated event: {}".format(json.dumps(event)))

        s3_pointer_content = {
            "function-arn": event["function-arn"],
            "payload": event["payload"],
            "aws-request-id": context.aws_request_id,
            "queued-function": context.function_name,
            "queued-timestamp": int(time.time()),
            "queued-log-group": context.log_group_name,
            "queued-log-stream": context.log_stream_name
        }

        self.s3_bucket.put_object(
            Body = json.dumps(s3_pointer_content, indent=4),
            Key = "queued/{}/{}.json".format(
                event["execution-time"],
                context.aws_request_id
            )
        )

        return {
            "message": "Lambda invocation queued successfully."
        }

    def validate_event(self, unvalidated_event):
        clean_event = {}

        execution_datetime = None
        execution_time_specified = unvalidated_event.get("execution-time")
        try:
            execution_time_seconds = int(execution_time_specified)
            execution_datetime = datetime.datetime.fromtimestamp(execution_time_seconds)
        except:
            pass

        if execution_datetime is None:
            raise Exception("Parameter \"{}\" must be specified as the number of seconds since UNIX epoch.".format("execution-time"))

        clean_event["execution-time"] = execution_datetime.strftime(datetime_string_format)

        lambda_function_arn = None
        lambda_function_specified = unvalidated_event.get("function-name")

        if lambda_function_specified is None:
            raise Exception("Parameter \"{}\" must be specified as the name or ARN of a Lambda function.".format("function-name"))

        lambda_client = boto3.client("lambda")

        if lambda_function_specified is not None:
            try:
                response = lambda_client.get_function(
                    FunctionName = lambda_function_specified
                )
                lambda_function_arn = response["Configuration"]["FunctionArn"]
            except botocore.exceptions.ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    raise Exception("Function \"{}\" not found.".format(lambda_function_specified))
                else:
                    raise

        clean_event["function-arn"] = lambda_function_arn

        lambda_payload = unvalidated_event.get("payload", {})

        if not isinstance(lambda_payload, dict):
            try:
                lambda_payload = json.loads(lambda_payload)
            except:
                pass

        if not isinstance(lambda_payload, dict):
            raise Exception("Parameter \"{}\" must be specified as a JSON key/value struct (dictionary).".format("payload"))

        clean_event["payload"] = lambda_payload

        return clean_event

    def get_own_cloudformation_metadata(self):

        if hasattr(self, "_own_cloudformation_metadata"):
            return self._own_cloudformation_metadata

        caller_arn = boto3.client("sts").get_caller_identity()["Arn"]
        caller_role = caller_arn.split(":")[5].split("/")[1]

        policy_response = boto3.client("iam").get_role_policy(
            RoleName = caller_role,
            PolicyName = "InvocationQueuerFunctionRoleActions"
        )

        this_stack_id = None

        for each_statement in policy_response["PolicyDocument"]["Statement"]:
            if len(each_statement.get("Action", [])) == 0:
                continue

            if each_statement["Action"][0].lower() == "cloudformation:describeStackResource".lower():
                this_stack_id = each_statement["Resource"]
                break

        if this_stack_id is None:
            raise Exception("Unable to determine CloudFormation stack ID from IAM policy.")
        
        response = boto3.client("cloudformation").describe_stack_resource(
            StackName = this_stack_id,
            LogicalResourceId = "InvocationQueuerFunction"
        )

        own_metadata = json.loads(response["StackResourceDetail"]["Metadata"])

        print("Own CloudFormation metadata: {}".format(json.dumps(own_metadata)))

        self._own_cloudformation_metadata = own_metadata

        return own_metadata

    def get_s3_bucket_name(self):
        return self.get_own_cloudformation_metadata()["SharedBucket"]


handler_object = None
def lambda_handler(event, context):
    global handler_object

    if handler_object is None:
        handler_object = LambdaHandler(context)

    return handler_object.handle_event(event, context)