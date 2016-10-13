from __future__ import print_function

import os, sys, unittest, uuid, datetime, importlib, logging

logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('nose').setLevel(logging.WARNING)

os.environ["AWS_DEFAULT_REGION"] = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

stubber_arg_lists = {}

def create_boto3_client_with_stubber(*args, **kwargs):
    import boto3
    from botocore.stub import Stubber
    
    new_client = boto3.client(*args, **kwargs)
    
    service_name = args[0]
    
    if service_name in stubber_arg_lists:
        new_stubber = Stubber(new_client)
        stubber_args = stubber_arg_lists[service_name]
        
        for each_invocation_set in stubber_args:
            method_name, args, kwargs = tuple(each_invocation_set)
            each_method = getattr(new_stubber, method_name)
            each_method(*args, **kwargs)
        
        stubber_arg_lists[service_name] = []
        
        new_stubber.activate()
    
    return new_client

class LambdaFunctionTestCase(unittest.TestCase):
    
    def __init__(self, *args, **kwargs):
        super(LambdaFunctionTestCase, self).__init__(*args, **kwargs)
    
    def setUp(self):
        self.added_module_paths = []
        
        paths_to_add = [
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "../build"),
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "../build/{}".format(self.function_name))
        ]
        
        for each_path_to_add in paths_to_add:
            if each_path_to_add not in sys.path:
                self.added_module_paths.append(each_path_to_add)
                sys.path.append(each_path_to_add)
        
        lambda_function_module = eval("importlib.import_module('{}.index')".format(self.function_name))
        
        self.lambda_function = lambda_function_module
        
        if hasattr(self.lambda_function, "boto3"):
            self.lambda_function.boto3.client = create_boto3_client_with_stubber
    
    def tearDown(self):
        for each_path in self.added_module_paths:
            sys.path.remove(each_path)
    
    def setup_boto3_stubber(self, service_name, method_name, *args, **kwargs):
        if service_name not in stubber_arg_lists:
            stubber_arg_lists[service_name] = []
        stubber_arg_lists[service_name].append((method_name, args, kwargs))
    

class LambdaContext(object):
    
    def __init__(self, new_function_name=None):
        self.function_name = new_function_name or "LambdaTestFunction"
        self.function_version = "$LATEST"
        self.invoked_function_arn = "arn:aws:lambda:us-east-1:000000000000:function:{}".format(self.function_name)
        self.aws_request_id = "{}".format(uuid.uuid4())
        self.client_context = None
        self.identity = None
        self.log_group_name = "/aws/lambda/{}".format(self.function_name)
        self.log_stream_name = "{}/[$LATEST]{}".format(
            datetime.datetime.utcnow().strftime("%Y/%m/%d"),
            uuid.uuid4()
        )
        self.memory_limit_in_mb = 128
    
    def get_remaining_time_millis():
        return 9999
    
    def log():
        raise NotImplementedException()
    
    

def generate_lambda_context(function_name=None):
    new_context = LambdaContext(function_name)
    
    return new_context