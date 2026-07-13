import unittest

from model_client import (
    add_chat_template_kwargs,
    parse_bounded_int,
    parse_training_content,
    strip_think_content,
    validate_model_config,
)


SCORE = '<!--SCORE\n{"professionalism":80,"communication":81,"needs_analysis":82,"objection_handling":83,"closing":84,"mood":"happy","mood_reason":"ok"}\n-->'


class ModelClientTests(unittest.TestCase):
    def test_think_blocks_complete_repeated_and_unterminated(self):
        self.assertEqual(strip_think_content('<think>secret</think>客户答复'), '客户答复')
        self.assertEqual(strip_think_content('<think>a</think><think>b</think>客户答复'), '客户答复')
        self.assertEqual(strip_think_content('客户答复<think>unfinished'), '客户答复')
        self.assertEqual(strip_think_content('</think>客户答复'), '客户答复')

    def test_only_think_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'MODEL_OUTPUT_EMPTY'):
            parse_training_content('<think>internal only</think>')

    def test_normal_and_fallback_output(self):
        parsed = parse_training_content('客户答复\n<!--COACH\n继续追问\n-->\n' + SCORE, 'stop')
        self.assertEqual(parsed['customer_reply'], '客户答复')
        self.assertEqual(parsed['coach_feedback'], '继续追问')
        self.assertEqual(parsed['score']['closing'], 84)
        self.assertEqual(parsed['parse_status'], 'ok')
        report = parse_training_content('结束语\n<!--REPORT\n完整复盘\n-->\n' + SCORE, 'stop')
        self.assertIn('<!--REPORT', report['content'])
        self.assertNotIn('完整复盘', report['customer_reply'])
        fallback = parse_training_content('只有客户答复', 'length')
        self.assertIn('coach', fallback['parse_status'])
        self.assertIn('score', fallback['parse_status'])
        self.assertIn('truncated', fallback['parse_status'])

    def test_qwen_thinking_switch_and_config_validation(self):
        payload = add_chat_template_kwargs({'model': 'Qwen3-32B'}, False)
        self.assertEqual(payload['chat_template_kwargs'], {'enable_thinking': False})
        self.assertEqual(parse_bounded_int('invalid', 1000, 256, 4096), 1000)
        self.assertTrue(validate_model_config('http://model.local/v1', 'secret', 'Qwen3-32B').configured)
        for base, key, model in [('', '', ''), ('https://internal-model.example.com/v1', 'replace-with-secret', 'replace-with-model-name'), ('http://model/v1/chat/completions', 'secret', 'model')]:
            self.assertFalse(validate_model_config(base, key, model).configured)


if __name__ == '__main__':
    unittest.main()
