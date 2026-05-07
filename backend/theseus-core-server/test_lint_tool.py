import os
import sys
import json
import pytest

# Add custom_tools to sys.path to allow importing the tool
sys.path.append(os.path.join(os.getcwd(), "theseus_engine", "custom_tools"))

from linter_parser import LinterParserTool, LinterParserToolInput


@pytest.mark.asyncio
async def test_flake8_parsing():
    tool = LinterParserTool()
    raw_output = (
        "path/to/file.py:10:5: E302 expected 2 blank lines\n"
        "path/to/file.py:20:1: F401 module imported but unused"
    )

    input_data = LinterParserToolInput(
        raw_output=raw_output, linter_type="flake8"
    )
    result = await tool.execute(input_data, None)

    parsed_data = json.loads(result.output)
    assert len(parsed_data) == 2
    assert parsed_data[0]["line"] == 10
    assert parsed_data[0]["code"] == "E302"
    assert parsed_data[1]["code"] == "F401"


@pytest.mark.asyncio
async def test_pylint_json_parsing():
    tool = LinterParserTool()
    pylint_json = json.dumps([
        {
            "path": "test.py",
            "line": 5,
            "column": 0,
            "symbol": "unused-import",
            "message": "Unused import test"
        }
    ])

    input_data = LinterParserToolInput(
        raw_output=pylint_json, linter_type="pylint"
    )
    result = await tool.execute(input_data, None)

    parsed_data = json.loads(result.output)
    assert len(parsed_data) == 1
    assert parsed_data[0]["line"] == 5
    assert parsed_data[0]["code"] == "unused-import"


@pytest.mark.asyncio
async def test_empty_output():
    tool = LinterParserTool()
    input_data = LinterParserToolInput(raw_output="", linter_type="flake8")
    result = await tool.execute(input_data, None)
    assert result.output == "[]"


@pytest.mark.asyncio
async def test_unsupported_linter():
    tool = LinterParserTool()
    input_data = LinterParserToolInput(
        raw_output="some output", linter_type="mypy"
    )
    result = await tool.execute(input_data, None)
    assert result.is_error is True
    assert "Unsupported linter" in result.output
