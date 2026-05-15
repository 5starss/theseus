"""Packaged runner entrypoint for editor distributions."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _load_env_files() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return

    candidates: list[Path] = [Path.cwd() / ".env"]
    core_root = os.getenv("THESEUS_CORE_ROOT", "").strip()
    if core_root:
        candidates.append(Path(core_root) / ".env")
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / ".env")
    else:
        candidates.append(Path(__file__).resolve().parents[1] / ".env")

    seen: set[str] = set()
    for candidate in candidates:
        key = os.path.normcase(str(candidate.resolve()))
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            load_dotenv(candidate, override=False)


def _usage() -> str:
    return (
        "Usage: theseus-runner <daemon|stdio> [args]\n\n"
        "Commands:\n"
        "  daemon  Start the local HTTP/SSE daemon.\n"
        "  stdio   Start the JSON Lines stdio runner.\n"
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(_usage(), file=sys.stderr)
        return 0

    _load_env_files()
    command = args.pop(0).lower()
    if command in {"daemon", "serve"}:
        from theseus_engine.daemon import main as daemon_main

        return daemon_main(args)
    if command in {"stdio", "json", "json-mode"}:
        from theseus_engine.cli_runner import main as cli_runner_main

        if "--json-mode" not in args:
            args.insert(0, "--json-mode")
        return cli_runner_main(args)

    print(f"Unknown theseus-runner command: {command}", file=sys.stderr)
    print(_usage(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
