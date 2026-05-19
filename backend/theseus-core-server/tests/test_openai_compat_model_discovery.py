from __future__ import annotations

import os
import types
import unittest
from unittest.mock import patch

from theseus_engine.wrappers.llm_clients.openai_compat_client import (
    TheseusOpenAICompatClient,
    _extract_model_ids,
    _select_served_model,
)
from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient


class _FakeModels:
    def __init__(self, response) -> None:
        self.response = response

    async def list(self):
        return self.response


class _FakeClient:
    def __init__(self, response) -> None:
        self.models = _FakeModels(response)


class OpenAICompatModelDiscoveryTest(unittest.IsolatedAsyncioTestCase):
    def test_extract_model_ids_accepts_openai_objects_and_dicts(self) -> None:
        response = {
            "data": [
                {"id": "default"},
                types.SimpleNamespace(id="google/gemma-4-26B-A4B-it"),
                {"id": ""},
                {},
            ]
        }

        self.assertEqual(
            _extract_model_ids(response),
            ["default", "google/gemma-4-26B-A4B-it"],
        )

    def test_select_served_model_prefers_exact_requested_model(self) -> None:
        self.assertEqual(
            _select_served_model(
                "google/gemma-4-26B-A4B-it",
                ["default", "google/gemma-4-26B-A4B-it"],
                preferred_model="default",
            ),
            "google/gemma-4-26B-A4B-it",
        )

    def test_select_served_model_uses_preferred_then_first_available(self) -> None:
        self.assertEqual(
            _select_served_model(
                "missing-model",
                ["first", "preferred"],
                preferred_model="preferred",
            ),
            "preferred",
        )
        self.assertEqual(
            _select_served_model("missing-model", ["first", "second"]),
            "first",
        )

    async def test_auto_discover_resolves_and_caches_served_model(self) -> None:
        client = TheseusOpenAICompatClient(
            api_key="test",
            base_url="http://localhost:8000/v1",
            auto_discover_model=True,
        )
        client._client = _FakeClient({"data": [{"id": "served-model"}]})

        self.assertEqual(await client._resolve_served_model("vllm"), "served-model")
        client._client = _FakeClient({"data": [{"id": "other-model"}]})
        self.assertEqual(await client._resolve_served_model("vllm"), "served-model")

    def test_vllm_prefix_enables_model_auto_discovery(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_BASE_URL": "http://localhost:8000/v1",
                "OPENAI_API_KEY": "vllm",
            },
            clear=False,
        ):
            client = TheseusLLMClient("vllm")

        backend = client._backend
        self.assertIsInstance(backend, TheseusOpenAICompatClient)
        self.assertTrue(backend._auto_discover_model)


if __name__ == "__main__":
    unittest.main()
