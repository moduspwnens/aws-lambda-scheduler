from __future__ import print_function

import sys, os, json, unittest, datetime
from local_helpers import LambdaFunctionTestCase, generate_lambda_context

class Test(LambdaFunctionTestCase):
    
    def __init__(self, *args, **kwargs):
        super(Test, self).__init__(*args, **kwargs)
        self.function_name = "InvocationQueuerFunction"
    
    def setUp(self):
        super(Test, self).setUp()

    def test_warming(self):
        
        sample_event = {
            "warming": True
        }
    
        response = self.lambda_function.lambda_handler(
            sample_event,
            generate_lambda_context()
        )
    
        assert len(response.keys()) == 1
        assert "message" in response
        assert response["message"] == "Function warmed successfully."
    
    def test_get_own_cloudformation_metadata(self):
        
        get_caller_response = {
            "Arn": "arn:aws:sts::000000000000:assumed-role/lambda-scheduler-default-InvocationQueuerFunctionR-JQ45FDD5Q2WO/awslambda_758_20161013002721546",
            "Account": "000000000000",
            "UserId": "ABCDEFGHIJKLM01234567"
        }
        
        caller_role = get_caller_response["Arn"].split(":")[5].split("/")[1]
        
        self.setup_boto3_stubber(
            "sts",
            "add_response",
            "get_caller_identity",
            get_caller_response
        )
        
        stack_id = "arn:aws:cloudformation:us-east-1:000000000000:stack/lambda-scheduler-default/1ca91760-90db-11e6-9765-5044334e0ab3"
        
        get_role_policy_response = {
        	"RoleName": "lambda-scheduler-default-InvocationQueuerFunctionR-JQ45FDD5Q2WO",
        	"PolicyDocument": json.dumps({
        		"Version": "2012-10-17",
        		"Statement": [{
        			"Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
        			"Resource": "arn:aws:logs:us-east-1:000000000000:log-group:/aws/lambda/lambda-scheduler-default-InvocationQueuerFunction-S1Q633SVQCLY:log-stream:*",
        			"Effect": "Allow"
        		}, {
        			"Action": ["iam:GetRolePolicy"],
        			"Resource": "arn:aws:iam::000000000000:role/lambda-scheduler-default-InvocationQueuerFunctionR-JQ45FDD5Q2WO",
        			"Effect": "Allow"
        		}, {
        			"Action": ["cloudformation:DescribeStackResource"],
        			"Resource": stack_id,
        			"Effect": "Allow"
        		}]
        	}),
        	"ResponseMetadata": {
        		"RetryAttempts": 0,
        		"HTTPStatusCode": 200,
        		"RequestId": "14092fba-90dc-11e6-87f6-2353897ef6fe",
        		"HTTPHeaders": {
        			"x-amzn-requestid": "14092fba-90dc-11e6-87f6-2353897ef6fe",
        			"date": "Thu, 13 Oct 2016 00:29:17 GMT",
        			"content-length": "1672",
        			"content-type": "text/xml"
        		}
        	},
        	"PolicyName": "InvocationQueuerFunctionRoleActions"
        }
        expected_params = {
            "RoleName": caller_role,
            "PolicyName": "InvocationQueuerFunctionRoleActions"
        }
        
        self.setup_boto3_stubber(
            "iam",
            "add_response",
            "get_role_policy",
            get_role_policy_response,
            expected_params
        )
        
        cloudformation_metadata_object = {
            "SharedBucket": "lambda-scheduler-default-sharedbucket-ch7n9ibykc7g"
        }
        
        get_stack_resource_response = {
        	"StackResourceDetail": {
        		"StackId": "arn:aws:cloudformation:us-east-1:299858126506:stack/lambda-scheduler-default/1ca91760-90db-11e6-9765-5044334e0ab3",
        		"ResourceStatus": "CREATE_COMPLETE",
        		"ResourceType": "AWS::Lambda::Function",
        		"LastUpdatedTimestamp": datetime.datetime(2016, 10, 13, 0, 23, 42, 351000),
        		"StackName": "lambda-scheduler-default",
        		"PhysicalResourceId": "lambda-scheduler-default-InvocationQueuerFunction-S1Q633SVQCLY",
        		"Metadata": json.dumps(cloudformation_metadata_object),
        		"LogicalResourceId": "InvocationQueuerFunction"
        	},
        	"ResponseMetadata": {
        		"RetryAttempts": 0,
        		"HTTPStatusCode": 200,
        		"RequestId": "c084c3d0-90dc-11e6-ac13-99ca095ca6aa",
        		"HTTPHeaders": {
        			"x-amzn-requestid": "c084c3d0-90dc-11e6-ac13-99ca095ca6aa",
        			"date": "Thu, 13 Oct 2016 00:34:07 GMT",
        			"content-length": "1029",
        			"content-type": "text/xml"
        		}
        	}
        }
        expected_params = {
            "StackName": stack_id,
            "LogicalResourceId": "InvocationQueuerFunction"
        }
        
        self.setup_boto3_stubber(
            "cloudformation",
            "add_response",
            "describe_stack_resource",
            get_stack_resource_response,
            expected_params
        )
        
        
        handler_object = self.lambda_function.LambdaHandler(generate_lambda_context())
        response = handler_object.get_own_cloudformation_metadata()
        
        assert response == cloudformation_metadata_object