"""
tests/test_state.py — Tests for format_value and SAMPLE_STATE from cli.py
"""
from insight_tf.state import format_value, SAMPLE_STATE

# ── SAMPLE_STATE ──────────────────────────────────────────────────────────────

def test_sample_state_has_required_keys():
    for key in ("version", "terraform_version", "serial", "resources"):
        assert key in SAMPLE_STATE

def test_sample_state_has_resources():
    assert len(SAMPLE_STATE["resources"]) > 0

def test_sample_state_resources_have_type_and_name():
    for r in SAMPLE_STATE["resources"]:
        assert "type" in r
        assert "name" in r

def test_sample_state_resources_have_instances():
    for r in SAMPLE_STATE["resources"]:
        assert "instances" in r
        assert isinstance(r["instances"], list)

def test_sample_state_terraform_version_is_string():
    assert isinstance(SAMPLE_STATE["terraform_version"], str)
    assert len(SAMPLE_STATE["terraform_version"]) > 0

def test_sample_state_serial_is_int():
    assert isinstance(SAMPLE_STATE["serial"], int)


# ── format_value ──────────────────────────────────────────────────────────────

def test_format_value_string():
    assert format_value("hello") == "hello"

def test_format_value_int():
    assert format_value(42) == "42"

def test_format_value_bool():
    assert format_value(True) == "True"

def test_format_value_none():
    assert format_value(None) == "None"

def test_format_value_empty_list():
    assert format_value([]) == "[]"

def test_format_value_list():
    result = format_value(["a", "b"])
    assert "[" in result
    assert "a" in result
    assert "b" in result

def test_format_value_dict():
    result = format_value({"key": "value"})
    assert "{" in result
    assert "key" in result
    assert "value" in result

def test_format_value_nested_dict():
    result = format_value({"outer": {"inner": "val"}})
    assert "outer" in result
    assert "inner" in result
    assert "val" in result

def test_format_value_empty_dict():
    result = format_value({})
    assert "{" in result
    assert "}" in result

def test_format_value_list_of_dicts():
    result = format_value([{"port": 80}, {"port": 443}])
    assert "80" in result
    assert "443" in result
