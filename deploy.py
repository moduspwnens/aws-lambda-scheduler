#!/usr/bin/env python

from __future__ import print_function

import os, sys, time, shutil, zipfile, subprocess, argparse, json, tempfile
import hashlib, logging

try:
    from urllib2 import urlopen
except:
    from urllib.request import urlopen

parser = argparse.ArgumentParser()
parser.add_argument("--stack-name", default="lambda-scheduler-default", help="Name for the CloudFormation stack.")
parser.add_argument("--clean", action="store_true", help="Remove all build artifacts first.")
parser.add_argument("--build-lambda-functions-only", action="store_true", help="Just build the Lambda functions and exit.")


s3_lambda_upload_prefix = "lambda/"
repo_dir = os.path.dirname(os.path.realpath(__file__))
cf_template_path = os.path.join(repo_dir, "lambda-scheduler.yaml")
s3_template_upload_key = "cf-stack-template.yaml"
build_dir = os.path.join(repo_dir, "build")
deploy_venv_dir = os.path.join(build_dir, "deploy-venv")
deploy_pip_dir = os.path.join(build_dir, "deploy-pip")
functions_source_dir = os.path.join(repo_dir, "lambda/functions")

sys.path.insert(1, deploy_pip_dir)

def create_deploy_virtualenv():
    
    import pip
    
    virtualenv_install_verified = False
    try:
        exit_code = pip.main(["show", "virtualenv"])
        virtualenv_install_verified = (exit_code == 0)
    except:
        pass
    
    if not virtualenv_install_verified:
        print("Installing virtualenv.")
        
        exit_code = pip.main(["install", "-t", deploy_pip_dir, "virtualenv"])
        
        if exit_code != 0:
            raise Exception("Non-zero exit code ({}) received from attempted virtualenv install.".format(exit_code))
    
    print("Creating virtualenv.")
    p = subprocess.Popen(
        [sys.executable, os.path.join(deploy_pip_dir, "virtualenv.py"), deploy_venv_dir]
    )
    
    exit_code = p.wait()
    if exit_code != 0:
        raise Exception("Non-zero exit code ({}) received from attempted virtualenv creation.".format(exit_code))

def install_local_pip():
        
        print("Installing pip.")
        
        pip_installer_script_content = urlopen("https://bootstrap.pypa.io/get-pip.py").read()
        
        temp_file_path = None
        with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
            temp_file_path = tmpfile.name
        
        open(temp_file_path, "w").write(pip_installer_script_content)
        
        os.makedirs(deploy_pip_dir)
        
        p = subprocess.Popen(
            [sys.executable, temp_file_path, "-t", deploy_pip_dir]
        )
        exit_code = p.wait()
        
        os.unlink(temp_file_path)
        
        if exit_code != 0:
            raise Exception("Non-zero exit code ({}) received from attempted pip install.".format(exit_code))

def verify_deploy_env():
    
    if not os.path.isdir(deploy_pip_dir):
        install_local_pip()
    
    if not os.path.isdir(deploy_venv_dir):
        create_deploy_virtualenv()
    
    # Windows
    venv_activate_script_path = os.path.join(deploy_venv_dir, "Scripts", "activate_this.py")
    
    # Everything else
    if not os.path.exists(venv_activate_script_path):
        venv_activate_script_path = os.path.join(deploy_venv_dir, "bin", "activate_this.py")
    
    execfile(venv_activate_script_path, dict(__file__=venv_activate_script_path))
    
    # Windows
    venv_pip_path = os.path.join(deploy_venv_dir, "Scripts", "pip")
    
    # Everything else
    if not os.path.exists(venv_pip_path):
        venv_pip_path = os.path.join(deploy_venv_dir, "bin", "pip")
    
    p = subprocess.Popen(
        [
            venv_pip_path,
            "install",
            "-r",
            os.path.join(repo_dir, "deploy-requirements.txt")
        ]
    )
    
    exit_code = p.wait()
    
    if exit_code != 0:
        raise Exception("Non-zero exit code ({}) received from attempted deployment dependencies install.".format(exit_code))

def verify_aws_credentials_set():
    caller_identity_arn = boto3.client("sts").get_caller_identity()["Arn"]

def ensure_build_dir_exists():
    if not os.path.isdir(build_dir):
        try:
            print("Creating build directory.")
            os.makedirs(build_dir)
        except:
            raise Exception("Error creating build directory at {}.".format(build_dir))

def build_lambda_function_environments():
    
    import checksumdir
    
    function_source_dir_list = []

    for dir_name, subdir_list, file_list in os.walk(functions_source_dir):
        if dir_name != functions_source_dir:
            break
    
        for each_subdir in subdir_list:
            function_source_dir_list.append(os.path.join(dir_name, each_subdir))

    for each_function_source_dir in function_source_dir_list:
    
        each_function_name = each_function_source_dir.split("/")[-1]
        
        each_function_build_metadata_file_path = os.path.join(build_dir, "{}.json".format(each_function_name))
        
        each_function_previous_build_metadata = {
            "source": "",
            "zip": ""
        }
        
        if os.path.exists(each_function_build_metadata_file_path):
            each_function_previous_build_metadata = json.loads(open(each_function_build_metadata_file_path).read())
        
        source_dir_hash = checksumdir.dirhash(each_function_source_dir)
        
        zip_output_path = os.path.join(build_dir, "{}.zip".format(each_function_name))
        
        if os.path.exists(zip_output_path):
            if each_function_previous_build_metadata["source"] == source_dir_hash:
                if file_md5_checksum(zip_output_path) == each_function_previous_build_metadata["zip"]:
                    print("{} already built.".format(each_function_name))
                    continue
        
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
        
        new_build_metadata = {
            "source": source_dir_hash,
            "zip": file_md5_checksum(zip_output_path)
        }
        
        open(each_function_build_metadata_file_path, "w").write(json.dumps(new_build_metadata, indent=4))
    
        print("Successfully built Lambda function: {}.".format(each_function_name))
    
    return function_source_dir_list


def create_base_cloudformation_stack(cf_stack_name):

    '''
        Create "base" CloudFormation template containing only the S3 bucket and the Lambda 
        function that deletes its objects on stack deletion.

        This gives us a bucket to put the full template and Lambda function ZIPs into while 
        still keeping the stack in a state where the resources will be deleted if the user 
        deletes the stack.
    '''

    cf_template_object = yaml.load(open(cf_template_path))
    for each_key in cf_template_object.keys():
        if each_key not in ["AWSTemplateFormatVersion", "Outputs", "Description", "Resources", "Parameters"]:
            del cf_template_object[each_key]

    for each_key in cf_template_object.get("Parameters", {}).keys():
        if each_key != "LogRetentionDays":
            del cf_template_object["Parameters"][each_key]

    for each_key in cf_template_object.get("Outputs", {}).keys():
        if each_key != "SharedBucket":
            del cf_template_object["Outputs"][each_key]

    base_resources_list = [
        # The bucket into which we'll load additional resources.
        "SharedBucket", 
    
        # The Lambda function that clears out the S3 bucket when deleted.
        "StackCleanupFunction",
        "StackCleanupFunctionRole",
        "StackCleanupFunctionRoleActions",
        "StackCleanupFunctionLogGroup",
        "StackCleanupInvocation"
    ]

    for each_key in cf_template_object.get("Resources", {}).keys():
        if each_key not in base_resources_list:
            del cf_template_object["Resources"][each_key]

    cf_template_object["Description"] = "Initial Deployment: {}".format(cf_template_object["Description"])

    cloudformation_client = boto3.client("cloudformation")
    response = cloudformation_client.create_stack(
        StackName = cf_stack_name,
        TemplateBody = json.dumps(cf_template_object, indent=4),
        Capabilities = ["CAPABILITY_IAM"]
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
    
    return stack_id, s3_bucket_name

def upload_lambda_function_deployment_packages(s3_bucket_name, function_source_dir_list):

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

def update_base_stack_to_full_stack(stack_id, s3_bucket_name):

    print("Updating stack's template with full content.")
    
    cloudformation_client = boto3.client("cloudformation")
    cloudformation_client.update_stack(
        StackName = stack_id,
        TemplateURL = "https://s3.amazonaws.com/{}/{}".format(
            s3_bucket_name,
            s3_template_upload_key
        ),
        UsePreviousTemplate = False,
        Capabilities = ["CAPABILITY_IAM"]
    )

    last_status = "UPDATE_IN_PROGRESS"

    while True:
        response = cloudformation_client.describe_stacks(
            StackName = stack_id
        )
    
        this_stack = response["Stacks"][0]
    
        last_status = this_stack["StackStatus"]
    
        print(" > Stack status: {}".format(last_status))
    
        if last_status not in ["UPDATE_IN_PROGRESS", "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS"]:
            break
    
        time.sleep(10)

    if last_status != "UPDATE_COMPLETE":
        raise Exception("Stack reached unexpected status: {}".format(last_status))

def file_md5_checksum(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

if __name__ == "__main__":
    
    args = parser.parse_args()
    
    if args.clean and os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    
    ensure_build_dir_exists()
    
    verify_deploy_env()
    
    function_source_dir_list = build_lambda_function_environments()
    
    if args.build_lambda_functions_only:
        sys.exit(0)
        
    import boto3, yaml
    
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    
    verify_aws_credentials_set()
    
    stack_id, s3_bucket_name = create_base_cloudformation_stack(args.stack_name)
    
    upload_lambda_function_deployment_packages(s3_bucket_name, function_source_dir_list)
    
    update_base_stack_to_full_stack(stack_id, s3_bucket_name)
    
    print("Deploy complete.")