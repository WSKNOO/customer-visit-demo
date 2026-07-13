import unittest

from research_cli import _safe_filename, validate_payload


class ResearchInputSecurityTests(unittest.TestCase):
    def test_valid_company(self):
        result = validate_payload({"company_name": "示例科技（北京）有限公司"})
        self.assertEqual(result["company_name"], "示例科技（北京）有限公司")

    def test_command_and_path_payloads_are_rejected(self):
        payloads = [
            "示例;id",
            "示例&&id",
            "示例|id",
            "示例$(id)",
            "示例`id`",
            "示例\nid",
            "../../etc/passwd",
            "..\\..\\Windows\\win.ini",
        ]
        for value in payloads:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_payload({"company_name": value})

    def test_filename_never_contains_path_separator(self):
        name = _safe_filename("示例/../客户")
        self.assertNotIn("/", name)
        self.assertNotIn("\\", name)
        self.assertNotIn("..", name)


if __name__ == "__main__":
    unittest.main()
