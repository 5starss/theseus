import inspect
import os
import sys
import types
import unittest
from unittest.mock import patch

from theseus_engine.observability.tracer import (
    is_tracing_enabled,
    reset_tracing_cache,
    theseus_traceable,
)


def fake_langsmith_module() -> types.ModuleType:
    module = types.ModuleType("langsmith")

    def traceable(**trace_kwargs):
        def decorator(func):
            inspect.signature(func)

            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            wrapper.trace_kwargs = trace_kwargs
            return wrapper

        return decorator

    module.traceable = traceable
    return module


class TheseusTraceableDescriptorTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_tracing_cache()

    def tearDown(self) -> None:
        reset_tracing_cache()

    def test_traceable_preserves_classmethod_descriptor(self):
        with patch.dict(
            os.environ,
            {
                "LANGCHAIN_API_KEY": "test-key",
                "THESEUS_TRACING_ENABLED": "true",
            },
        ):
            with patch.dict(
                sys.modules, {"langsmith": fake_langsmith_module()}
            ):
                reset_tracing_cache()

                class SampleValidator:
                    @theseus_traceable(
                        run_type="tool",
                        name="sample_classmethod",
                    )
                    @classmethod
                    def validate(cls, value: str):
                        return cls.__name__, value

                self.assertEqual(
                    SampleValidator.validate("ok"),
                    ("SampleValidator", "ok"),
                )

    def test_traceable_preserves_staticmethod_descriptor(self):
        with patch.dict(
            os.environ,
            {
                "LANGCHAIN_API_KEY": "test-key",
                "THESEUS_TRACING_ENABLED": "true",
            },
        ):
            with patch.dict(
                sys.modules, {"langsmith": fake_langsmith_module()}
            ):
                reset_tracing_cache()

                class SampleValidator:
                    @theseus_traceable(
                        run_type="tool",
                        name="sample_staticmethod",
                    )
                    @staticmethod
                    def validate(value: str):
                        return value

                self.assertEqual(SampleValidator.validate("ok"), "ok")

    def test_langchain_tracing_v2_false_bypasses_tracing(self):
        with patch.dict(
            os.environ,
            {
                "LANGCHAIN_API_KEY": "test-key",
                "THESEUS_TRACING_ENABLED": "true",
                "LANGCHAIN_TRACING_V2": "false",
            },
        ):
            reset_tracing_cache()

            self.assertFalse(is_tracing_enabled())

            def sample(value: str) -> str:
                return value

            decorated = theseus_traceable(
                run_type="tool",
                name="bypassed",
            )(sample)

            self.assertIs(decorated, sample)

    def test_langchain_tracing_v2_unset_preserves_existing_opt_in(self):
        with patch.dict(
            os.environ,
            {
                "LANGCHAIN_API_KEY": "test-key",
                "THESEUS_TRACING_ENABLED": "true",
            },
            clear=True,
        ):
            reset_tracing_cache()

            self.assertTrue(is_tracing_enabled())


if __name__ == "__main__":
    unittest.main()
