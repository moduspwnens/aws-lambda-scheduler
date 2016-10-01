#!/usr/bin/env python

from __future__ import print_function

import os, sys, shutil, zipfile, subprocess

s3_lambda_upload_prefix = "lambda/"
deployment_name = os.environ.get("DEPLOYMENT_ID", "default")

cf_stack_name = "lambda-scheduler-{}".format(deployment_name)

try:
    import pip
except:
    raise Exception("Unable to load pip. Is it installed? See https://pip.pypa.io/en/stable/installing/")

try:
    import boto3
except:
    raise Exception("Unable to load boto3. Try \"pip install boto3\".")

repo_dir = os.path.dirname(os.path.realpath(__file__))

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
    function_build_dir = os.path.join(build_dir, each_function_name)
    
    if os.path.exists(function_build_dir):
        shutil.rmtree(function_build_dir)
    
    shutil.copytree(each_function_source_dir, function_build_dir)
    
    pip_requirements_path = os.path.join(function_build_dir, "requirements.txt")
    
    if os.path.exists(pip_requirements_path):
        exit_code = pip.main(["install", "-r", pip_requirements_path, "-t", function_build_dir])
        if exit_code != 0:
            sys.exit(1)
    
    build_zip_path = os.path.join(build_dir, each_function_name)
    if os.path.exists("{}.zip".format(build_zip_path)):
        os.unlink("{}.zip".format(build_zip_path))
    
    shutil.make_archive(build_zip_path, "zip", function_build_dir)
    
    print("Successfully built Lambda function: {}.".format(each_function_name))
    
caller_identity_arn = boto3.client("sts").get_caller_identity()["Arn"]
print("AWS Identity: {}".format(caller_identity_arn))
