from __future__ import print_function

import sys, os, unittest
from local_helpers import LambdaFunctionTestCase, generate_lambda_context

class Test(LambdaFunctionTestCase):
    
    def __init__(self, *args, **kwargs):
        super(Test, self).__init__(*args, **kwargs)
        self.function_name = "InvocationQueuerFunction"

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