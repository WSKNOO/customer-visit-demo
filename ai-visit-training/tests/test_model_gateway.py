import unittest
from unittest.mock import Mock, patch

import requests

import app as training
from model_client import ModelConfigStatus


VALID_CONTENT = '客户答复\n<!--COACH\n继续追问\n-->\n<!--SCORE\n{"professionalism":80,"communication":80,"needs_analysis":80,"objection_handling":80,"closing":80,"mood":"neutral","mood_reason":"ok"}\n-->'


class ModelGatewayTests(unittest.TestCase):
    def setUp(self):
        self.values = {name: getattr(training, name) for name in ['MOCK_MODE', 'MODEL_CONFIG_STATUS', 'MODEL_MAX_RETRIES', 'TRAINING_MODEL_ENABLE_THINKING']}
        training.MOCK_MODE = False
        training.MODEL_CONFIG_STATUS = ModelConfigStatus(True, None)
        training.MODEL_MAX_RETRIES = 0
        training.TRAINING_MODEL_ENABLE_THINKING = False

    def tearDown(self):
        for name, value in self.values.items():
            setattr(training, name, value)

    def response(self, status, payload):
        result = Mock(status_code=status, text='upstream response')
        result.json.return_value = payload
        return result

    @patch.object(training.requests, 'post')
    def test_request_disables_thinking(self, post):
        post.return_value = self.response(200, {'choices': [{'message': {'content': VALID_CONTENT}, 'finish_reason': 'stop'}]})
        result = training.call_deepseek([{'role': 'user', 'content': 'hello'}])
        self.assertTrue(result['success'])
        self.assertEqual(post.call_args.kwargs['json']['chat_template_kwargs'], {'enable_thinking': False})

    @patch.object(training.requests, 'post', side_effect=requests.Timeout())
    def test_timeout(self, _post):
        self.assertEqual(training.call_deepseek([{'role': 'user', 'content': 'hello'}])['error_code'], 'MODEL_TIMEOUT')

    @patch.object(training.requests, 'post')
    def test_401_and_500_are_safe(self, post):
        post.return_value = self.response(401, {'error': {'message': 'internal detail'}})
        self.assertEqual(training.call_deepseek([{'role': 'user', 'content': 'hello'}])['error_code'], 'MODEL_AUTH_FAILED')
        post.return_value = self.response(500, {'error': {'message': 'internal detail'}})
        self.assertEqual(training.call_deepseek([{'role': 'user', 'content': 'hello'}])['error_code'], 'MODEL_UPSTREAM_ERROR')

    def test_mock_regression_uses_no_network(self):
        training.MOCK_MODE = True
        with patch.object(training.requests, 'post') as post:
            result = training.call_deepseek([{'role': 'user', 'content': 'hello'}])
        self.assertTrue(result['success'])
        post.assert_not_called()


if __name__ == '__main__':
    unittest.main()
