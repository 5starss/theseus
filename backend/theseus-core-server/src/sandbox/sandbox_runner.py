import json
import os
import sys
import traceback

INPUT_PATH = "/sandbox/input/payload.json"
CODE_PATH = "/sandbox/input/tool_code.py"
RESULT_PATH = "/sandbox/output/result.json"


def _write_result(payload: dict) -> None:
    os.makedirs(os.path.dirname(RESULT_PATH), exist_ok=True)
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def main() -> int:
    try:
        with open(INPUT_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)

        namespace: dict = {}
        with open(CODE_PATH, "r", encoding="utf-8") as f:
            code = compile(f.read(), CODE_PATH, "exec")
        exec(code, namespace)

        tool_main = namespace.get("main")
        if not callable(tool_main):
            raise RuntimeError("tool_code.py must define a callable main(payload) function")

        result = tool_main(payload)
        _write_result(
            {
                "success": True,
                "result": result,
            }
        )
        return 0
    except Exception as exc:
        _write_result(
            {
                "success": False,
                "error_message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
