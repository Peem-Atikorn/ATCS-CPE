import asyncio
import unittest
from unittest.mock import patch

import httpx

from app.clients import ServiceClients
from app.router import UpstreamError


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_gemini_only_is_not_labeled_fallback(self):
        class FakeCompletions:
            async def create(self, **kwargs):
                return type("Response", (), {
                    "choices": [type("Choice", (), {"message": type("Message", (), {
                        "content": '{"intent": "trivia_history", "confidence": 0.9}'})()})()],
                    "usage": None})()

        class FakeOpenAI:
            def __init__(self, **kwargs):
                self.chat = type("Chat", (), {"completions": FakeCompletions()})()

        with patch.dict("os.environ", {"GROQ_API_KEY": "", "GROQ_MODEL": "",
                                    "GEMINI_API_KEY": "test", "GEMINI_MODEL": "test"}), \
             patch("openai.AsyncOpenAI", FakeOpenAI):
            result = await ServiceClients(None).llm_decide("question", "req")
        self.assertIsNone(result["fallback"])

    async def test_gemini_is_tried_after_groq_stalls(self):
        calls = []

        class FakeCompletions:
            def __init__(self, provider):
                self.provider = provider

            async def create(self, **kwargs):
                calls.append(self.provider)
                if self.provider == "groq":
                    await asyncio.sleep(1)
                return type("Response", (), {
                    "choices": [type("Choice", (), {"message": type("Message", (), {
                        "content": '{"intent": "trivia_history", "confidence": 0.9}'})()})()],
                    "usage": None})()

        class FakeOpenAI:
            def __init__(self, **kwargs):
                provider = "groq" if "groq.com" in kwargs["base_url"] else "gemini"
                self.chat = type("Chat", (), {"completions": FakeCompletions(provider)})()

        with patch.dict("os.environ", {"GROQ_API_KEY": "test", "GROQ_MODEL": "test",
                                    "GEMINI_API_KEY": "test", "GEMINI_MODEL": "test"}), \
             patch("openai.AsyncOpenAI", FakeOpenAI), \
             patch("app.clients.LLM_PROVIDER_TIMEOUT", 0.01, create=True):
            result = await asyncio.wait_for(ServiceClients(None).llm_decide("question", "req"), 0.5)
        self.assertEqual(calls, ["groq", "gemini"])
        self.assertEqual(result["fallback"], "llm_fallback_provider")

    async def test_invalid_team_payload_uses_upstream_fallback(self):
        for payload in ([{"team_id": 1}], {"teams": [{"team_id": "bad", "name": "A",
                                                        "short_name": "A"}]}):
            with self.subTest(payload=payload):
                async def handler(request):
                    return httpx.Response(200, json=payload)

                async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
                    with self.assertRaises(UpstreamError):
                        await ServiceClients(http).get_teams()


if __name__ == "__main__":
    unittest.main()


class LlmPromptTests(unittest.IsolatedAsyncioTestCase):
    async def test_llm_prompt_lists_every_contract_intent(self):
        seen = {}

        class FakeCompletions:
            async def create(self, **kwargs):
                seen["system"] = kwargs["messages"][0]["content"]
                return type("Response", (), {
                    "choices": [type("Choice", (), {"message": type("Message", (), {
                        "content": '{"intent": "player_info", "confidence": 0.9}'})()})()],
                    "usage": None})()

        class FakeOpenAI:
            def __init__(self, **kwargs):
                self.chat = type("Chat", (), {"completions": FakeCompletions()})()

        with patch.dict("os.environ", {"GROQ_API_KEY": "test", "GROQ_MODEL": "test",
                                    "GEMINI_API_KEY": "", "GEMINI_MODEL": ""}),              patch("openai.AsyncOpenAI", FakeOpenAI):
            result = await ServiceClients(None).llm_decide("who plays for arsenal", "req")
        for intent in ("trivia_history", "match_result", "fixture_schedule", "standings_stats",
                       "weekly_summary", "player_info", "general_football", "prediction",
                       "out_of_scope", "clarify"):
            self.assertIn(intent, seen["system"])
        self.assertIn("current-season top scorer", seen["system"])
        self.assertIn("not league-wide rankings", seen["system"])
        self.assertEqual(result["intent"], "player_info")


def fake_openai(content, seen):
    class FakeCompletions:
        async def create(self, **kwargs):
            seen.update(kwargs)
            return type("Response", (), {
                "choices": [type("Choice", (), {"message": type("Message", (), {"content": content})()})()],
                "usage": type("Usage", (), {"prompt_tokens": 11, "completion_tokens": 4})()})()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    return FakeOpenAI


GROQ_ONLY = {"GROQ_API_KEY": "test", "GROQ_MODEL": "test", "GEMINI_API_KEY": "", "GEMINI_MODEL": ""}


class CondenseClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_condense_sends_recent_trimmed_history(self):
        seen = {}
        history = [{"role": "user" if index % 2 == 0 else "assistant", "content": f"m{index} " + "x" * 400}
                   for index in range(8)]
        reply = '{"standalone_query": "ใครยิงให้ลิเวอร์พูล", "changed": true}'
        with patch.dict("os.environ", GROQ_ONLY), patch("openai.AsyncOpenAI", fake_openai(reply, seen)):
            result = await ServiceClients(None).condense("แล้วใครยิง", history, "req")
        self.assertEqual(result["standalone_query"], "ใครยิงให้ลิเวอร์พูล")
        self.assertEqual(result["token_usage"], {"input": 11, "output": 4})
        self.assertEqual(seen["temperature"], 0)
        self.assertIn("Never answer", seen["messages"][0]["content"])
        user = seen["messages"][1]["content"]
        self.assertNotIn("m0 ", user)
        self.assertNotIn("m1 ", user)
        self.assertIn("User: m2 ", user)
        self.assertIn("Assistant: m7 ", user)
        self.assertNotIn("x" * 300, user)
        self.assertTrue(user.endswith("Latest question: แล้วใครยิง"))

    async def test_condense_without_standalone_query_is_value_error(self):
        with patch.dict("os.environ", GROQ_ONLY), patch("openai.AsyncOpenAI", fake_openai('{"changed": false}', {})):
            with self.assertRaises(ValueError):
                await ServiceClients(None).condense("แล้วใครยิง", [], "req")

    async def test_condense_without_providers_is_upstream_error(self):
        with patch.dict("os.environ", {"GROQ_API_KEY": "", "GROQ_MODEL": "",
                                       "GEMINI_API_KEY": "", "GEMINI_MODEL": ""}):
            with self.assertRaises(UpstreamError):
                await ServiceClients(None).condense("แล้วใครยิง", [], "req")
