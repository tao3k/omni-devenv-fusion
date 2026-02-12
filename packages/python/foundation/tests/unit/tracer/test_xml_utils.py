"""Tests for shared tracer XML helpers."""

from __future__ import annotations

from omni.tracer.xml import escape_xml, extract_attr, extract_tag


def test_escape_xml_escapes_special_chars():
    raw = "<a>&\"'</a>"
    assert escape_xml(raw) == "&lt;a&gt;&amp;&quot;&apos;&lt;/a&gt;"


def test_extract_tag_returns_inner_text():
    xml = "<root><content>Hello</content></root>"
    assert extract_tag(xml, "content") == "Hello"


def test_extract_attr_returns_value():
    xml = '<quality score="0.80" delta="+0.10"/>'
    assert extract_attr(xml, "quality", "score") == "0.80"
