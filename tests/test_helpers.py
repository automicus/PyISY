"""Tests for :mod:`pyisy.helpers`."""

from __future__ import annotations

from xml.dom import minidom

from pyisy.helpers import (
    EventEmitter,
    attr_from_element,
    attr_from_xml,
    value_from_nested_xml,
    value_from_xml,
)


def test_value_from_xml_returns_text() -> None:
    doc = minidom.parseString("<root><a>hello</a></root>")
    assert value_from_xml(doc, "a") == "hello"


def test_value_from_xml_returns_default_when_missing() -> None:
    doc = minidom.parseString("<root><a>x</a></root>")
    assert value_from_xml(doc, "missing", "fallback") == "fallback"


def test_attr_from_element_reads_attribute() -> None:
    doc = minidom.parseString('<root id="42" name="N"/>')
    assert attr_from_element(doc.documentElement, "id") == "42"
    assert attr_from_element(doc.documentElement, "name") == "N"


def test_attr_from_xml_reads_nested_attribute() -> None:
    doc = minidom.parseString('<root><child kind="leaf"/></root>')
    assert attr_from_xml(doc, "child", "kind") == "leaf"


def test_value_from_nested_xml_walks_path() -> None:
    doc = minidom.parseString("<root><a><b>deep</b></a></root>")
    assert value_from_nested_xml(doc, ["a", "b"]) == "deep"


def test_event_emitter_subscribe_and_notify() -> None:
    emitter = EventEmitter()
    received: list[object] = []
    sub = emitter.subscribe(received.append)
    emitter.notify("ping")
    emitter.notify(42)
    sub.unsubscribe()
    emitter.notify("after-unsubscribe")
    assert received == ["ping", 42]


def test_event_emitter_filtered_subscription() -> None:
    emitter = EventEmitter()
    seen: list[str] = []
    emitter.subscribe(seen.append, event_filter="only-me")
    emitter.notify("other")
    emitter.notify("only-me")
    assert seen == ["only-me"]
