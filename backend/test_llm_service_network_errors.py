import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))
sys.path.insert(0, str(Path(__file__).parent))

import requests
import llm_service


class GeminiNetworkErrorTests(unittest.TestCase):
    def test_api_key_is_sent_in_header_not_url(self):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "{}"}]}}]
        }

        with patch("llm_service.requests.post", return_value=response) as post:
            result, model = llm_service.call_gemini_api("secret-api-key", "prompt")

        self.assertEqual(result, {})
        self.assertEqual(model, "gemini-3.1-flash-lite")
        request_url = post.call_args.args[0]
        request_headers = post.call_args.kwargs["headers"]
        self.assertNotIn("secret-api-key", request_url)
        self.assertNotIn("?key=", request_url)
        self.assertEqual(request_headers["x-goog-api-key"], "secret-api-key")

    @patch("time.sleep", return_value=None)
    def test_dns_failure_retries_same_endpoint_and_returns_safe_error(self, _sleep):
        key = "secret-api-key"
        raw_error = requests.exceptions.ConnectionError(
            "Failed to resolve generativelanguage.googleapis.com "
            "for https://generativelanguage.googleapis.com/v1beta/models/example:generateContent?key=secret-api-key"
        )

        with patch("llm_service.requests.post", side_effect=raw_error) as post:
            with self.assertRaises(llm_service.AIProviderNetworkError) as raised:
                llm_service.call_gemini_api(key, "prompt")

        self.assertEqual(post.call_count, 3)
        internal_message = str(raised.exception)
        self.assertNotIn(key, internal_message)
        self.assertIn("[REDACTED]", internal_message)

        user_message = llm_service.format_ai_error_for_user(raised.exception)
        self.assertIn("not an API-key error", user_message)
        self.assertNotIn(key, user_message)

    def test_connectivity_check_does_not_leak_key(self):
        key = "secret-api-key"
        network_error = requests.exceptions.ConnectionError("temporary DNS failure")

        with patch("llm_service.get_available_llm_provider", return_value=("gemini", key)), \
             patch("llm_service.requests.post", side_effect=network_error) as post:
            status = llm_service.test_ai_key_connectivity()

        self.assertEqual(status["status"], "network_error")
        self.assertNotIn(key, status["message"])
        self.assertNotIn(key, post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["headers"]["x-goog-api-key"], key)


if __name__ == "__main__":
    unittest.main()
