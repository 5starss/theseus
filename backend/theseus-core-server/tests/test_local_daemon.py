import os
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from theseus_engine.daemon import (
    MAX_EVENTS_PER_RUN,
    RUNNER_STATE_SCHEMA_VERSION,
    DaemonState,
    RunState,
    create_app,
    resolve_model,
)


class FakeSessions:
    current_name = "default"


class FakeRuntime:
    sessions = FakeSessions()

    async def initialize(self):
        return [{"type": "RunnerReady", "mode": "local-daemon", "session": "default"}]

    async def submit(self, text):
        yield {"type": "AssistantTextDelta", "text": f"echo:{text}"}
        yield {"type": "AssistantTurnComplete", "message": {"role": "assistant"}, "usage": {}}


class FailingRuntime:
    sessions = FakeSessions()

    async def initialize(self):
        raise RuntimeError("Gemini API key is not configured. Set GEMINI_API_KEY or GOOGLE_API_KEY before starting Theseus.")


class BlockingRuntime:
    sessions = FakeSessions()

    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def initialize(self):
        return []

    async def submit(self, text):
        self.started.set()
        await self.release.wait()
        yield {"type": "AssistantTextDelta", "text": f"echo:{text}"}


class LocalDaemonTests(unittest.IsolatedAsyncioTestCase):
    def make_client(self, tmp_path: Path):
        state = DaemonState(
            workspace=tmp_path,
            token="test-token",
            model="test-model",
            user_level=5,
            runtime_factory=FakeRuntime,
        )
        transport = httpx.ASGITransport(app=create_app(state))
        return httpx.AsyncClient(transport=transport, base_url="http://testserver")

    async def test_daemon_requires_bearer_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            async with self.make_client(Path(tmp)) as client:
                response = await client.get("/health")

                self.assertEqual(response.status_code, 401)

    async def test_daemon_health_and_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            async with self.make_client(Path(tmp)) as client:
                headers = {"Authorization": "Bearer test-token"}

                health = await client.get("/health", headers=headers)
                status = await client.get("/status", headers=headers)

                self.assertEqual(health.status_code, 200)
                self.assertEqual(health.json()["mode"], "local-daemon")
                self.assertEqual(health.json()["schemaVersion"], RUNNER_STATE_SCHEMA_VERSION)
                self.assertEqual(status.status_code, 200)
                self.assertEqual(status.json()["schemaVersion"], RUNNER_STATE_SCHEMA_VERSION)
                self.assertEqual(status.json()["workspaceCwd"], str(Path(tmp)))

    async def test_daemon_run_streams_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            async with self.make_client(Path(tmp)) as client:
                headers = {"Authorization": "Bearer test-token"}

                created = await client.post("/runs", headers=headers, json={"text": "hello"})

                self.assertEqual(created.status_code, 200)
                run_id = created.json()["runId"]
                async with client.stream("GET", f"/runs/{run_id}/events", headers=headers) as response:
                    chunks = [chunk async for chunk in response.aiter_text()]
                    body = "".join(chunks)

                self.assertEqual(response.status_code, 200)
                self.assertIn("AssistantTextDelta", body)
                self.assertIn("echo:hello", body)

    async def test_daemon_permission_prompt_waits_for_extension_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = DaemonState(
                workspace=Path(tmp),
                token="test-token",
                model="test-model",
                user_level=5,
                runtime_factory=FakeRuntime,
            )
            run = RunState(run_id="run-permission", text="hello")
            state.runs[run.run_id] = run
            transport = httpx.ASGITransport(app=create_app(state))
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                token = state._permission_run.set(run)
                try:
                    prompt_task = asyncio.create_task(
                        state.permission_prompt("bash", "위험한 명령 실행")
                    )
                    for _ in range(50):
                        if run.events:
                            break
                        await asyncio.sleep(0.01)

                    self.assertTrue(run.events)
                    event = run.events[0]
                    self.assertEqual(event["type"], "PermissionRequest")
                    self.assertEqual(event["run_id"], run.run_id)
                    request_id = event["request_id"]

                    response = await client.post(
                        f"/runs/{run.run_id}/permissions/{request_id}",
                        headers={"Authorization": "Bearer test-token"},
                        json={"approved": True},
                    )
                    approved = await asyncio.wait_for(prompt_task, timeout=1)
                finally:
                    state._permission_run.reset(token)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(approved)

    async def test_daemon_run_replays_events_after_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            async with self.make_client(Path(tmp)) as client:
                headers = {"Authorization": "Bearer test-token"}

                created = await client.post("/runs", headers=headers, json={"text": "hello"})

                self.assertEqual(created.status_code, 200)
                run_id = created.json()["runId"]
                async with client.stream("GET", f"/runs/{run_id}/events?after=1", headers=headers) as response:
                    chunks = [chunk async for chunk in response.aiter_text()]
                    body = "".join(chunks)

                self.assertEqual(response.status_code, 200)
                self.assertNotIn("AssistantTextDelta", body)
                self.assertIn("AssistantTurnComplete", body)

    async def test_daemon_rejects_concurrent_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = BlockingRuntime()
            state = DaemonState(
                workspace=Path(tmp),
                token="test-token",
                model="test-model",
                user_level=5,
                runtime_factory=lambda: runtime,
            )
            transport = httpx.ASGITransport(app=create_app(state))
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                headers = {"Authorization": "Bearer test-token"}
                created = await client.post(
                    "/runs", headers=headers, json={"text": "hello"}
                )
                self.assertEqual(created.status_code, 200)
                await runtime.started.wait()

                rejected = await client.post(
                    "/runs", headers=headers, json={"text": "again"}
                )

            runtime.release.set()
            first_run = state.runs[created.json()["runId"]]
            if first_run.task is not None:
                await first_run.task

        self.assertEqual(rejected.status_code, 409)
        self.assertIn("이미 실행 중인 run", rejected.json()["detail"])

    async def test_daemon_event_buffer_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = DaemonState(
                workspace=Path(tmp),
                token="test-token",
                model="test-model",
                user_level=5,
                runtime_factory=FakeRuntime,
            )
            run = RunState(run_id="run-test", text="hello")
            state.runs[run.run_id] = run

            for index in range(MAX_EVENTS_PER_RUN + 3):
                await state._append(run, {"type": "Event", "index": index})

        self.assertEqual(len(run.events), MAX_EVENTS_PER_RUN)
        self.assertEqual(run.event_offset, 3)
        self.assertEqual(state.status()["runs"][0]["eventCount"], MAX_EVENTS_PER_RUN + 3)
        self.assertEqual(state.status()["runs"][0]["eventOffset"], 3)

    async def test_daemon_returns_startup_failure_as_http_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = DaemonState(
                workspace=Path(tmp),
                token="test-token",
                model="test-model",
                user_level=5,
                runtime_factory=FailingRuntime,
            )
            transport = httpx.ASGITransport(app=create_app(state))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/runs",
                    headers={"Authorization": "Bearer test-token"},
                    json={"text": "hello"},
                )

            self.assertEqual(response.status_code, 503)
            self.assertIn("GEMINI_API_KEY", response.json()["detail"])

    async def test_daemon_resolves_model_from_legacy_env(self):
        with patch.dict(os.environ, {"OPENHARNESS_MODEL": "vllm/custom-model"}, clear=True):
            model = resolve_model("google/default-model")
            self.assertEqual(os.environ["THESEUS_MODEL"], "vllm/custom-model")
            self.assertEqual(os.environ["OPENHARNESS_MODEL"], "vllm/custom-model")

        self.assertEqual(model, "vllm/custom-model")

    async def test_daemon_prefers_theseus_model_env(self):
        with patch.dict(
            os.environ,
            {"THESEUS_MODEL": "openai/primary", "OPENHARNESS_MODEL": "vllm/legacy"},
            clear=True,
        ):
            model = resolve_model("google/default-model")

        self.assertEqual(model, "openai/primary")


if __name__ == "__main__":
    unittest.main()
