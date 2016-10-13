# Serverless AWS Lambda Scheduling API

[![Build Status](https://travis-ci.org/moduspwnens/aws-lambda-scheduler.svg?branch=master)](https://travis-ci.org/moduspwnens/aws-lambda-scheduler)

An easy-to-deploy, scalable API for scheduling the invocation of Lambda functions with no fixed costs.

Not yet functional--still a work in progress.

## Why?

AWS doesn't provide a way out-of-the-box for scheduling the execution of Lambda functions. However, there are plenty of use cases:
 * Moving / deleting DynamoDB data after it reaches a certain age
 * Terminating an instance after it's been stopped for a certain amount of time
 * Sending an e-mail a certain amount of time after an event occurs

You can work around these sometimes through a scheduled CloudWatch event, but even that has limits. You're limited on the amount of CloudWatch event rules you can have, you have to architect around the invocations being effectively stateless (you'd need to look up what e-mails to send, for example), and you're limited to one invocation per minute. 

This allows you to schedule the invocation of a Lambda function with a specific payload at a specific time. Or a lot of them, with lots of payloads at varying times.

## How to deploy

Deploy from your local machine. Just requires git and Python 2.7.

```
$ git clone https://github.com/moduspwnens/aws-lambda-scheduler.git
$ cd aws-lambda-scheduler
$ python deploy.py
```

Tested on Mac, Linux, and Windows.

All resources are contained as part of a CloudFormation stack, which you can view on the [CloudFormation web page](https://console.aws.amazon.com/cloudformation/home). To uninstall, simply delete the stack from here.

