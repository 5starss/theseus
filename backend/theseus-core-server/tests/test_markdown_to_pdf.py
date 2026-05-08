import pytest
from markdown_to_pdf_tool import MarkdownToPdfTool, MarkdownToPdfToolInput
from theseus_engine.tools.core.base_tools import ToolExecutionContext

@pytest.mark.asyncio
async def test_markdown_to_pdf_conversion():
    from pathlib import Path
    tool = MarkdownToPdfTool()
    context = ToolExecutionContext(cwd=Path.cwd())
    
    md_text = "# Title\n## Subtitle\nThis is a test.\n* Item 1\n* Item 2"
    output_path = "test_output.pdf"
    
    input_data = MarkdownToPdfToolInput(
        markdown_text=md_text,
        output_path=output_path
    )
    
    result = await tool.execute(input_data, context)
    
    assert result.is_error is False
    assert "Successfully saved PDF" in result.output
    
    import os
    assert os.path.exists(output_path)
    
    # Clean up
    if os.path.exists(output_path):
        os.remove(output_path)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_markdown_to_pdf_conversion())
