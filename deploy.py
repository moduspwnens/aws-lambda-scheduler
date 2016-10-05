#!/usr/bin/env python

from __future__ import print_function

import os, sys, time, shutil, zipfile, subprocess, argparse

parser = argparse.ArgumentParser()
parser.add_argument("--build-lambda-functions-only", action="store_true", help="Just build the Lambda functions and exit.")
args = parser.parse_args()

s3_lambda_upload_prefix = "lambda/"
deployment_name = os.environ.get("LS_DEPLOYMENT_ID", "default")

cf_stack_name = "lambda-scheduler-{}".format(deployment_name)

if not args.build_lambda_functions_only:
    try:
        import boto3
    except:
        raise Exception("Unable to load boto3. Try \"pip install boto3\".")

repo_dir = os.path.dirname(os.path.realpath(__file__))
cf_template_base_path = os.path.join(repo_dir, "lambda-scheduler-base.yaml")
cf_template_path = os.path.join(repo_dir, "lambda-scheduler.yaml")
s3_template_upload_key = "cf-stack-template.yaml"

build_dir = os.path.join(repo_dir, "build")

if not os.path.isdir(build_dir):
    try:
        print("Creating build directory.")
        os.makedirs(build_dir)
    except:
        raise Exception("Error creating build directory at {}.".format(build_dir))

functions_source_dir = os.path.join(repo_dir, "lambda/functions")

function_source_dir_list = []

for dir_name, subdir_list, file_list in os.walk(functions_source_dir):
    if dir_name != functions_source_dir:
        break
    
    for each_subdir in subdir_list:
        function_source_dir_list.append(os.path.join(dir_name, each_subdir))

for each_function_source_dir in function_source_dir_list:
    
    each_function_name = each_function_source_dir.split("/")[-1]
    
    print("Building Lambda function: {}".format(each_function_name))
    
    function_build_dir = os.path.join(build_dir, each_function_name)
    
    if os.path.exists(function_build_dir):
        shutil.rmtree(function_build_dir)
    
    shutil.copytree(each_function_source_dir, function_build_dir)
    
    pip_requirements_path = os.path.join(function_build_dir, "requirements.txt")
    
    if os.path.exists(pip_requirements_path):
        print("Installing dependencies.")
        p = subprocess.Popen(
            ["pip", "install", "-r", pip_requirements_path, "-t", function_build_dir],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        exit_code = p.wait()
        p_stdout, p_stderr = p.communicate()
        
        if exit_code != 0:
            print("pip invocation failed.", file=sys.stderr)
            print(p_stderr, file=sys.stderr)
            sys.exit(1)
    
    build_zip_path = os.path.join(build_dir, each_function_name)
    if os.path.exists("{}.zip".format(build_zip_path)):
        os.unlink("{}.zip".format(build_zip_path))
    
    shutil.make_archive(build_zip_path, "zip", function_build_dir)
    
    print("Successfully built Lambda function: {}.".format(each_function_name))

if args.build_lambda_functions_only:
    sys.exit(0)

caller_identity_arn = boto3.client("sts").get_caller_identity()["Arn"]
print("AWS Identity: {}".format(caller_identity_arn))

cloudformation_client = boto3.client("cloudformation")
response = cloudformation_client.create_stack(
    StackName = cf_stack_name,
    TemplateBody = open(cf_template_base_path).read()
)

stack_id = response["StackId"]

print("New CloudFormation Stack ID: {}".format(stack_id))

last_status = "CREATE_IN_PROGRESS"
s3_bucket_name = None

while True:
    response = cloudformation_client.describe_stacks(
        StackName = stack_id
    )
    
    this_stack = response["Stacks"][0]
    
    last_status = this_stack["StackStatus"]
    
    print(" > Stack status: {}".format(last_status))
    
    if last_status != "CREATE_IN_PROGRESS":
        for each_output_pair in this_stack.get("Outputs", []):
            if each_output_pair["OutputKey"] == "SharedBucket":
                s3_bucket_name = each_output_pair["OutputValue"]
                break
        
        break
    
    time.sleep(10)

if last_status != "CREATE_COMPLETE":
    raise Exception("Stack reached unexpected status: {}".format(last_status))

if s3_bucket_name is None:
    raise Exception("Unabled to find shared S3 bucket name in stack outputs.")

print("Shared S3 bucket: {}".format(s3_bucket_name))

s3_client = boto3.client("s3")
s3_client.put_object(
    Body = open(cf_template_path),
    Bucket = s3_bucket_name,
    Key = s3_template_upload_key
)

for each_function_source_dir in function_source_dir_list:
    
    each_function_name = each_function_source_dir.split("/")[-1]
    
    build_zip_path = os.path.join(build_dir, each_function_name)
    
    print("Uploading {}.zip.".format(each_function_name))
    
    s3_client.put_object(
        Body = open("{}.zip".format(build_zip_path)),
        Bucket = s3_bucket_name,
        Key = "lambda/{}.zip".format(each_function_name)
    )

cloudformation_client.update_stack(
    StackName = stack_id,
    TemplateURL = "https://s3.amazonaws.com/{}/{}".format(
        s3_bucket_name,
        s3_template_upload_key
    ),
    UsePreviousTemplate = False,
    Capabilities = ["CAPABILITY_NAMED_IAM"]
)

last_status = "UPDATE_IN_PROGRESS"

while True:
    response = cloudformation_client.describe_stacks(
        StackName = stack_id
    )
    
    this_stack = response["Stacks"][0]
    
    last_status = this_stack["StackStatus"]
    
    print(" > Stack status: {}".format(last_status))
    
    if last_status != "UPDATE_IN_PROGRESS":
        break
    
    time.sleep(10)

if last_status != "UPDATE_COMPLETE":
    raise Exception("Stack reached unexpected status: {}".format(last_status))

print("Deploy complete.")