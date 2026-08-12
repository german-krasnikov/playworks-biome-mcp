"""Tests for JUnit XML writer (cli/junit.py)."""
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def test_junit_empty_suite():
    """Empty suite produces valid XML with 0 tests."""
    from luna_mcp.cli.junit import JUnitWriter
    w = JUnitWriter("my_suite")
    root = w.build()
    assert root.tag == "testsuite"
    assert root.get("name") == "my_suite"
    assert root.get("tests") == "0"
    assert root.get("failures") == "0"
    assert root.get("errors") == "0"


def test_junit_all_pass():
    """All-pass suite: N testcases, no failure/error children."""
    from luna_mcp.cli.junit import JUnitWriter
    w = JUnitWriter("ci")
    w.add_pass("baseline_a")
    w.add_pass("baseline_b")
    root = w.build()
    cases = root.findall("testcase")
    assert len(cases) == 2
    assert root.get("tests") == "2"
    assert root.get("failures") == "0"
    for tc in cases:
        assert tc.find("failure") is None
        assert tc.find("error") is None


def test_junit_with_failure():
    """Failed testcase has <failure> child."""
    from luna_mcp.cli.junit import JUnitWriter
    w = JUnitWriter("ci")
    w.add_pass("baseline_a")
    w.add_failure("baseline_b", "pixel diff 5.2%")
    root = w.build()
    assert root.get("tests") == "2"
    assert root.get("failures") == "1"
    cases = {tc.get("name"): tc for tc in root.findall("testcase")}
    assert cases["baseline_a"].find("failure") is None
    fail_child = cases["baseline_b"].find("failure")
    assert fail_child is not None
    assert "pixel diff" in (fail_child.text or fail_child.get("message", ""))


def test_junit_with_error():
    """Error testcase has <error> child."""
    from luna_mcp.cli.junit import JUnitWriter
    w = JUnitWriter("ci")
    w.add_error("launch", "Chrome did not start")
    root = w.build()
    assert root.get("errors") == "1"
    tc = root.find("testcase[@name='launch']")
    assert tc is not None
    err_child = tc.find("error")
    assert err_child is not None


def test_junit_write_file_roundtrip():
    """Write XML to file and parse back correctly."""
    from luna_mcp.cli.junit import JUnitWriter
    w = JUnitWriter("roundtrip")
    w.add_pass("ok_test")
    w.add_failure("bad_test", "mismatch")
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        path = f.name
    try:
        w.write(path)
        tree = ET.parse(path)
        root = tree.getroot()
        assert root.tag == "testsuite"
        assert len(root.findall("testcase")) == 2
    finally:
        Path(path).unlink(missing_ok=True)


# ── m1: JUnit XML must carry time attribute on testsuite and testcases ────────

def test_junit_testsuite_has_time_attribute():
    """m1: <testsuite> element must have a time attribute."""
    from luna_mcp.cli.junit import JUnitWriter
    w = JUnitWriter("ci")
    w.add_pass("a")
    root = w.build()
    assert root.get("time") is not None, "<testsuite> missing time attribute"


def test_junit_testcase_has_time_attribute():
    """m1: each <testcase> element must have a time attribute."""
    from luna_mcp.cli.junit import JUnitWriter
    w = JUnitWriter("ci")
    w.add_pass("a")
    w.add_failure("b", "oops")
    root = w.build()
    for tc in root.findall("testcase"):
        assert tc.get("time") is not None, f"<testcase name='{tc.get('name')}'> missing time attribute"


def test_junit_time_attribute_in_written_file():
    """m1: time attributes survive XML serialisation round-trip."""
    from luna_mcp.cli.junit import JUnitWriter
    w = JUnitWriter("ci")
    w.add_pass("ok")
    w.add_error("bad", "boom")
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        path = f.name
    try:
        w.write(path)
        root = ET.parse(path).getroot()
        assert root.get("time") is not None
        for tc in root.findall("testcase"):
            assert tc.get("time") is not None
    finally:
        Path(path).unlink(missing_ok=True)
