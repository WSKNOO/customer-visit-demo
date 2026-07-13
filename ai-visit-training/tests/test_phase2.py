import os
import tempfile
import unittest
from pathlib import Path

os.environ["MOCK_MODE"] = "true"
os.environ["VOICE_ENABLED"] = "false"
os.environ["TTS_ENABLED"] = "false"

import app as training_app
from app import app, resolve_resource_file, training_sessions
from visit_brief import validate_visit_brief


def sample_brief():
    return {
        "schema_version": "1.0",
        "brief_id": "mock-brief-1",
        "customer": {
            "name": "示例客户有限公司",
            "industry": "制造业",
            "profile_summary": "正在评估数据协同与智能化建设方向。",
        },
        "visit": {
            "goal": "了解数字化需求并确认试点范围",
            "focus_areas": ["数据治理", "智能制造"],
            "suggested_questions": ["当前数据协同的主要障碍是什么？"],
        },
        "signals": {
            "recent_events": ["发布数字化规划"],
            "digital_clues": ["正在建设数据平台"],
            "potential_needs": [{"summary": "提升数据质量", "basis": "inference"}],
            "recommended_solutions": [{"summary": "数据治理服务"}],
        },
        "sources": [{"title": "客户官网", "url": "https://example.com/news"}],
        "training_options": {
            "difficulty": "中等", "phase": "discovery", "round_limit": 3, "voice_enabled": False,
        },
    }


class VisitBriefTests(unittest.TestCase):
    def test_valid_brief_and_truncation(self):
        payload = sample_brief()
        payload["customer"]["profile_summary"] = "甲" * 3000
        result = validate_visit_brief(payload)
        self.assertEqual(len(result["customer"]["profile_summary"]), 2000)
        self.assertFalse(result["training_options"]["voice_enabled"])

    def test_invalid_types_and_internal_source_are_rejected(self):
        payload = sample_brief()
        payload["visit"]["focus_areas"] = "not-an-array"
        with self.assertRaises(ValueError):
            validate_visit_brief(payload)
        payload = sample_brief()
        payload["sources"][0]["url"] = "http://127.0.0.1/private"
        with self.assertRaises(ValueError):
            validate_visit_brief(payload)


class ResourceSecurityTests(unittest.TestCase):
    def test_traversal_absolute_windows_encoded_and_extension_rejected(self):
        with tempfile.TemporaryDirectory() as allowed, tempfile.TemporaryDirectory() as outside:
            allowed_path = Path(allowed)
            outside_path = Path(outside)
            (allowed_path / "ok.pdf").write_bytes(b"%PDF-test")
            (allowed_path / "bad.exe").write_bytes(b"bad")
            (outside_path / "secret.pdf").write_bytes(b"secret")
            (allowed_path / "escape.pdf").symlink_to(outside_path / "secret.pdf")

            self.assertEqual(resolve_resource_file("ok.pdf", roots=(allowed_path,)).name, "ok.pdf")
            for value in [
                "../../etc/passwd",
                "/etc/passwd",
                "C:\\Windows\\win.ini",
                "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
                "%252e%252e%252fetc%252fpasswd",
                "escape.pdf",
                "bad.exe",
            ]:
                with self.subTest(value=value):
                    with self.assertRaises(ValueError):
                        resolve_resource_file(value, roots=(allowed_path,))


class TrainingApiTests(unittest.TestCase):
    def setUp(self):
        training_sessions.clear()
        self.client = app.test_client()

    def test_health_and_voice_disabled(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.get_json()["mock"])
        self.assertFalse(health.get_json()["voice_enabled"])
        self.assertEqual(self.client.post("/api/asr", json={"audio": "AAAA"}).status_code, 503)

    def test_session_init_and_three_text_rounds(self):
        response = self.client.post("/api/training/session/init", json=sample_brief())
        self.assertEqual(response.status_code, 201)
        session = response.get_json()
        self.assertEqual(session["status"], "ready")
        self.assertEqual(session["customer_name"], "示例客户有限公司")
        self.assertIn(session["session_id"], training_sessions)
        loaded = self.client.get(f"/api/training/session/{session['session_id']}")
        self.assertEqual(loaded.status_code, 200)
        loaded_data = loaded.get_json()
        self.assertEqual(loaded_data["customer_name"], "示例客户有限公司")
        self.assertEqual(loaded_data["opening_question"], session["opening_question"])
        self.assertNotIn("context", loaded_data)

        messages = []
        last_content = ""
        for text in ["您好，我想先了解现状。", "我们建议先确认影响范围。", "可以先做一个小范围试点。"]:
            messages.append({"role": "user", "content": text})
            chat = self.client.post("/api/chat", json={"session_id": session["session_id"], "messages": messages})
            self.assertEqual(chat.status_code, 200)
            data = chat.get_json()
            self.assertTrue(data["success"])
            self.assertIn("<!--SCORE", data["content"])
            last_content = data["content"]
            messages.append({"role": "assistant", "content": data["content"]})
        self.assertIn("<!--REPORT", last_content)

    def test_invalid_session_payload_has_safe_error(self):
        response = self.client.post("/api/training/session/init", json={"customer": {}})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("Traceback", response.get_data(as_text=True))

    def test_demo_one_click_session_and_model_fallback(self):
        previous_demo = training_app.DEMO_MODE
        previous_mock = training_app.MOCK_MODE
        previous_status = training_app.MODEL_CONFIG_STATUS
        try:
            training_app.DEMO_MODE = True
            response = self.client.post('/api/demo/start')
            self.assertEqual(response.status_code, 201)
            demo = response.get_json()
            self.assertTrue(demo['demo_mode'])
            self.assertTrue(demo['opening_question'])
            self.assertTrue(demo['scene_id'].startswith('knowcard/'))

            training_app.MOCK_MODE = False
            training_app.MODEL_CONFIG_STATUS = training_app.validate_model_config('', '', '')
            chat = self.client.post('/api/chat', json={
                'session_id': demo['session_id'],
                'messages': [{'role': 'user', 'content': '请介绍一下试点建议。'}],
            }).get_json()
            self.assertTrue(chat['success'])
            self.assertTrue(chat['demo_fallback'])
            self.assertNotIn('MODEL_CONFIG_INVALID', chat.get('content', ''))
        finally:
            training_app.DEMO_MODE = previous_demo
            training_app.MOCK_MODE = previous_mock
            training_app.MODEL_CONFIG_STATUS = previous_status

    def test_tts_is_interface_only(self):
        response = self.client.post('/api/tts', json={'text': '测试'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()['error_code'], 'TTS_DISABLED')

        previous_tts = training_app.TTS_ENABLED
        try:
            training_app.TTS_ENABLED = True
            response = self.client.post('/api/tts', json={'text': '测试'})
            self.assertEqual(response.status_code, 501)
            self.assertEqual(response.get_json()['error_code'], 'TTS_NOT_CONFIGURED')
        finally:
            training_app.TTS_ENABLED = previous_tts


if __name__ == "__main__":
    unittest.main()
