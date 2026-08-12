"""Tests for lessons/keys.py — class_hash, sig_hash, make_key."""
from luna_mcp.lessons.keys import class_hash, make_key, sig_hash


def test_class_hash_stable_across_runs():
    h1 = class_hash("UnityEngine.UI.Button")
    h2 = class_hash("UnityEngine.UI.Button")
    assert h1 == h2


def test_class_hash_different_for_different_names():
    assert class_hash("UnityEngine.UI.Button") != class_hash("UnityEngine.UI.Image")


def test_class_hash_length_16():
    h = class_hash("SomeClass")
    assert len(h) == 16


def test_sig_hash_changes_on_field_rename():
    sig1 = {"methods": ["Play"], "fields": ["loop"]}
    sig2 = {"methods": ["Play"], "fields": ["looping"]}
    assert sig_hash(sig1) != sig_hash(sig2)


def test_sig_hash_stable_for_reordered_fields():
    sig1 = {"methods": ["Play", "Stop"], "fields": ["loop", "main"]}
    sig2 = {"methods": ["Stop", "Play"], "fields": ["main", "loop"]}
    assert sig_hash(sig1) == sig_hash(sig2)


def test_sig_hash_length_8():
    h = sig_hash({"methods": [], "fields": []})
    assert len(h) == 8


def test_make_key_returns_three_components():
    key = make_key("UnityEngine.UI.Button", {"methods": ["OnClick"], "fields": []}, "7.1.0")
    assert len(key) == 3
    ch, sh, tv = key
    assert len(ch) == 16
    assert len(sh) == 8
    assert tv == "7.1.0"


def test_make_key_default_typemap_version():
    ch, sh, tv = make_key("Foo", {})
    assert tv == ""
