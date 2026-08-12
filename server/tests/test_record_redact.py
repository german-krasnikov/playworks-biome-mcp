"""Tests for record/redact.py — RED phase."""
from luna_mcp.record.redact import redact_args, redact_result, redact_text


def test_redact_text_emails():
    result = redact_text("Contact user@example.com for help")
    assert "user@example.com" not in result
    assert "***@***" in result


def test_redact_text_jwt():
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.TJVA95"
    result = redact_text(f"token={jwt}")
    assert jwt not in result
    assert "***JWT***" in result


def test_redact_text_bearer():
    result = redact_text("Authorization: Bearer abc123secret")
    assert "abc123secret" not in result
    assert "Bearer ***" in result


def test_redact_text_kv_pattern():
    result = redact_text("token=mysecret&other=ok")
    assert "mysecret" not in result
    assert "token=***" in result


def test_redact_text_kv_password():
    result = redact_text("password=hunter2")
    assert "hunter2" not in result
    assert "password=***" in result


def test_redact_text_truncates_at_max_len():
    long = "a" * 600
    result = redact_text(long, max_len=100)
    assert len(result) < 600
    assert "truncated" in result
    assert "500" in result  # chars truncated count


def test_redact_text_empty():
    assert redact_text("") == ""
    assert redact_text(None) is None


def test_redact_args_replaces_sensitive_keys():
    args = {"token": "abc", "secret": "xyz", "other": "ok"}
    result = redact_args(args)
    assert result["token"] == "***"
    assert result["secret"] == "***"
    assert result["other"] == "ok"


def test_redact_args_case_insensitive():
    args = {"Token": "abc", "PASSWORD": "xyz"}
    result = redact_args(args)
    assert result["Token"] == "***"
    assert result["PASSWORD"] == "***"


def test_redact_args_recurses_strings():
    args = {"expression": "user@example.com is logged in"}
    result = redact_args(args)
    assert "user@example.com" not in result["expression"]


def test_redact_args_non_string_passthrough():
    args = {"count": 5, "enabled": True}
    result = redact_args(args)
    assert result["count"] == 5
    assert result["enabled"] is True


def test_redact_result_screenshot_drops_bytes():
    big_data = "data:image/png;base64," + "A" * 6000
    result = redact_result("screenshot", big_data)
    assert "data:image" not in result
    assert "<image:" in result
    assert "sha256=" in result
    assert "len=" in result


def test_redact_result_large_data_uri():
    big_data = "data:image/jpeg;base64," + "B" * 6000
    result = redact_result("screenshot_som", big_data)
    assert "<image:" in result


def test_redact_result_normal_text():
    result = redact_result("get_hierarchy", "node1\nnode2")
    assert "node1" in result


def test_redact_result_truncates_long_eval():
    long_result = "x" * 1000
    result = redact_result("eval_js", long_result)
    assert len(result) <= 600  # truncated at 500 + overhead


def test_redact_result_non_string():
    result = redact_result("ping", 42)
    assert isinstance(result, str)
    assert "42" in result


# RED: new patterns missing from current implementation

def test_redact_text_kv_header_style():
    """x-api-key: value — colon-separated HTTP header style."""
    result = redact_text("x-api-key: supersecret123")
    assert "supersecret123" not in result


def test_redact_text_openai_key():
    """sk-... OpenAI-style secret key."""
    result = redact_text("using key sk-abcdefghij1234567890ABCDEFGHIJ1234567890xxxx")
    assert "sk-abcdefghij" not in result


def test_redact_text_google_api_key():
    """AIza... Google API key format."""
    result = redact_text("google_key=AIzaSyB1234567890abcdefghijklmnopqrstuvw")
    assert "AIzaSyB1234567890" not in result


def test_redact_text_hex_token():
    """Long hex strings (32+ chars) — common bearer/session tokens."""
    result = redact_text("session=deadbeefcafebabe1234567890abcdef12345678")
    assert "deadbeefcafebabe" not in result


def test_redact_text_header_style_password():
    """password: value — generic header-style sensitive field."""
    result = redact_text("password: hunter2")
    assert "hunter2" not in result


def test_redact_text_header_style_preserves_innocuous():
    """Header style with non-sensitive key should NOT be redacted."""
    result = redact_text("content-type: application/json")
    assert "application/json" in result
