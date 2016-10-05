from __future__ import print_function

import json
import boto3
import cfnresponse

class LambdaHandler(object):

    def __init__(self, context):
        pass
  
    def handle_event(self, event, context):
        print("Event: {}".format(json.dumps(event)))
        
        if "warming" in event:
            return {
                "message": "Function warmed successfully."
            }
        
        request_type = event.get("RequestType")
        
        if request_type == "Create":
            self.handle_setup_event(event, context)
        elif request_type == "Delete":
            self.handle_cleanup_event(event, context)
        
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, None)
        
        return {}
    
    def handle_setup_event(self, event, context):
        return
    
    def handle_cleanup_event(self, event, context):
        
        s3_client = boto3.client("s3")
        s3_bucket_name = event["ResourceProperties"]["SharedBucket"]
        
        paginator = s3_client.get_paginator("list_objects_v2")
        
        response_iterator = paginator.paginate(
          Bucket = s3_bucket_name
        )
        
        for each_list_response in response_iterator:
          keys_to_delete = []
          
          for each_item in each_list_response.get("Contents", []):
              keys_to_delete.append(each_item["Key"])
          
          if len(keys_to_delete) == 0:
              print("Last request for objects in {} returned none.".format(
                  s3_bucket_name
              ))
              break
          
          print("Deleting {} object(s) from {}.".format(
              len(keys_to_delete),
              s3_bucket_name
          ))
          
          s3_client.delete_objects(
              Bucket = s3_bucket_name,
              Delete = {
                  "Objects": list({"Key": x} for x in keys_to_delete)
              }
          )
          
          print("Object(s) deleted.")

handler_object = None
def lambda_handler(event, context):
    global handler_object
    
    if handler_object is None:
        handler_object = LambdaHandler(context)
    
    return handler_object.handle_event(event, context)