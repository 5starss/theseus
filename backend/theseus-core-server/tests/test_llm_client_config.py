import os
import unittest
from unittest.mock import patch

from theseus_engine.wrappers.llm_clients.api_types import AuthenticationFailure
from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient


class LLMClientConfigTests(unittest.TestCase):
    def test_gemini_requires_provider_specific_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(AuthenticationFailure) as raised:
                TheseusLLMClient("google/gemini-2.5-pro")

        message = str(raised.exception)
        self.assertIn("Gemini API key is not configured", message)
        self.assertIn("GEMINI_API_KEY", message)
        self.assertIn("GOOGLE_API_KEY", message)

    def test_gemini_accepts_google_api_key_fallback(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "google-key"}, clear=True):
            with patch(
                "theseus_engine.wrappers.llm_clients.openai_compat_client.AsyncOpenAI"
            ) as async_openai:
                TheseusLLMClient("google/gemini-2.5-pro")

        kwargs = async_openai.call_args.kwargs
        self.assertEqual(kwargs["api_key"], "google-key")
        self.assertEqual(
            kwargs["base_url"],
            "https://generativelanguage.googleapis.com/v1beta/openai",
        )

    def test_gemini_skips_placeholder_key_before_fallback(self):
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "test", "GOOGLE_API_KEY": "google-key"},
            clear=True,
        ):
            with patch(
                "theseus_engine.wrappers.llm_clients.openai_compat_client.AsyncOpenAI"
            ) as async_openai:
                TheseusLLMClient("google/gemini-2.5-pro")

        self.assertEqual(async_openai.call_args.kwargs["api_key"], "google-key")

    def test_gemini_placeholder_key_fails_before_api_call(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}, clear=True):
            with self.assertRaises(AuthenticationFailure) as raised:
                TheseusLLMClient("google/gemini-2.5-pro")

        message = str(raised.exception)
        self.assertIn("Gemini API key is not configured", message)
        self.assertIn("Ignored placeholder values in GEMINI_API_KEY", message)


if __name__ == "__main__":
    unittest.main()
