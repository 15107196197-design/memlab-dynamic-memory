"""Provider adapter tests: OpenAI-compatible routing without network or keys."""
import json
import os
import unittest
from unittest import mock

from memlab import providers
from memlab.llm import EmbeddingClient, LLMClient


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "provider": "deepseek", "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1", "api_key_env": "DEEPSEEK_API_KEY",
            "temperature": 0.0,
        }

    def test_chat_request_and_usage(self):
        response = {"choices": [{"message": {"content": "hello"}}],
                    "usage": {"prompt_tokens": 11, "completion_tokens": 3}}
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "secret"}), \
                mock.patch("memlab.providers._request_json", return_value=response) as request:
            text, usage = providers.chat(self.env, "hi", max_tokens=8)
        self.assertEqual(text, "hello")
        self.assertEqual(usage, {"tokens_in": 11, "tokens_out": 3})
        url, body, headers = request.call_args.args
        self.assertEqual(url, "https://api.deepseek.com/v1/chat/completions")
        self.assertEqual(body["model"], "deepseek-chat")
        self.assertEqual(body["messages"][0]["content"], "hi")
        self.assertEqual(body["max_tokens"], 8)
        self.assertEqual(headers["Authorization"], "Bearer secret")

    def test_json_mode_parses_fenced_json(self):
        response = {"choices": [{"message": {"content": "```json\n{\"answer\": \"x\"}\n```"}}]}
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "secret"}), \
                mock.patch("memlab.providers._request_json", return_value=response):
            value, _ = providers.chat(self.env, "hi", json_mode=True)
        self.assertEqual(value, {"answer": "x"})

    def test_missing_key_fails_before_network(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("memlab.providers._request_json") as request:
                with self.assertRaises(providers.ProviderError):
                    providers.chat(self.env, "hi")
        request.assert_not_called()

    def test_llm_client_routes_to_provider(self):
        response = {"choices": [{"message": {"content": "ok"}}],
                    "usage": {"prompt_tokens": 2, "completion_tokens": 1}}
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "secret"}), \
                mock.patch("memlab.providers._request_json", return_value=response):
            client = LLMClient.from_environment(self.env)
            self.assertEqual(client.generate("q"), "ok")
        self.assertEqual(client.usage()["tokens_in"], 2)
        self.assertEqual(client.usage()["tokens_out"], 1)

    def test_fingerprint_does_not_include_key(self):
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "secret"}):
            client = LLMClient.from_environment(self.env)
        fingerprint = client.fingerprint()
        self.assertNotIn("secret", fingerprint)
        other = LLMClient.from_environment({**self.env, "model": "other-model"})
        self.assertNotEqual(fingerprint, other.fingerprint())

    def test_preflight_ollama_reports_missing_model(self):
        with mock.patch("memlab.providers._request_json", return_value={"models": [{"name": "other:latest"}]}):
            with self.assertRaises(providers.ProviderError) as caught:
                providers.preflight({"provider": "ollama", "model": "qwen3.8:27b-q4_K_M"})
        self.assertIn("ollama pull", str(caught.exception))

    def test_preflight_api_ready_with_key(self):
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "secret"}), \
                mock.patch("memlab.providers._request_json", return_value={"data": [{"id": "deepseek-chat"}]}):
            result = providers.preflight(self.env)
        self.assertTrue(result["ready"])
        self.assertEqual(result["models"], ["deepseek-chat"])
        self.assertNotIn("secret", json.dumps(result))

    def test_embedding_client_routes_to_provider(self):
        response = {"data": [{"embedding": [1.0, 2.0]}], "usage": {"prompt_tokens": 4}}
        env = {"provider": "deepseek", "model": "embed", "base_url": "https://api.deepseek.com/v1",
               "api_key_env": "DEEPSEEK_API_KEY"}
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "secret"}), \
                mock.patch("memlab.providers._request_json", return_value=response):
            client = EmbeddingClient.from_environment(env)
            self.assertEqual(client.embed(["a"]), [[1.0, 2.0]])


if __name__ == "__main__":
    unittest.main()
