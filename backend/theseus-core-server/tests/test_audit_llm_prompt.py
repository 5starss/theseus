from theseus_engine.wrappers.hooks.theseus_hook_executor import TheseusHookExecutor


def test_audit_prompt_formats_literal_json_examples():
    prompt = TheseusHookExecutor._AUDIT_PROMPT.format(
        arguments='{"file_path": "bogo.py"}'
    )

    assert '{"ok": true}' in prompt
    assert '{"ok": false, "reason": "..."}' in prompt
    assert '{"file_path": "bogo.py"}' in prompt


def test_audit_text_extraction_accepts_content_block_lists():
    executor = TheseusHookExecutor()

    raw = executor._extract_audit_text([
        {"type": "text", "text": '{"ok": true}'},
    ])

    assert raw == '{"ok": true}'
