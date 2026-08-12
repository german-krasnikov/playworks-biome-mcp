"""Tests for SymptomClassifier."""
import pytest

from luna_mcp.physics_detective.symptom_classifier import CATEGORIES, SymptomClassifier


@pytest.mark.asyncio
async def test_empty_symptom_returns_general():
    clf = SymptomClassifier()
    cat, conf, kw = await clf.classify("", [])
    assert cat == "general"
    assert conf == 0.0


@pytest.mark.asyncio
async def test_jitter_keywords():
    clf = SymptomClassifier()
    cat, conf, kw = await clf.classify("object is shaking and vibrate a lot", ["goblin"])
    assert cat == "jitter"
    assert conf > 0.5


@pytest.mark.asyncio
async def test_tunneling_keywords():
    clf = SymptomClassifier()
    cat, conf, kw = await clf.classify("ball falls through the floor", ["goblin"])
    assert cat == "tunneling"
    assert conf > 0.5


@pytest.mark.asyncio
async def test_explosion_keywords():
    clf = SymptomClassifier()
    cat, conf, kw = await clf.classify("cloth explode and stretch wildly", ["verlet"])
    assert cat == "explosion"
    assert conf > 0.5


@pytest.mark.asyncio
async def test_sleep_keywords():
    clf = SymptomClassifier()
    cat, conf, kw = await clf.classify("body doesn't wake up after impact", ["goblin"])
    assert cat == "sleep"
    assert conf > 0.5


@pytest.mark.asyncio
async def test_no_match_fallback_general():
    clf = SymptomClassifier()
    cat, conf, kw = await clf.classify("something weird with the physics", ["goblin"])
    assert cat == "general"
    assert conf <= 0.6


@pytest.mark.asyncio
async def test_sampling_disabled_fallback():
    """When sampling is provided but disabled, falls back to keyword."""
    class FakeSampling:
        enabled = False
        async def plan(self, *a, **kw):
            return None
    clf = SymptomClassifier(FakeSampling())
    cat, conf, kw = await clf.classify("rope explode from too much stiffness", ["verlet"])
    assert cat == "explosion"


@pytest.mark.asyncio
async def test_categories_covered():
    assert "jitter" in CATEGORIES
    assert "tunneling" in CATEGORIES
    assert "explosion" in CATEGORIES
    assert "general" in CATEGORIES


# M1: inflected forms must match
@pytest.mark.asyncio
async def test_classify_inflected_shaking():
    clf = SymptomClassifier()
    cat, conf, kw = await clf.classify("object is shaking", ["goblin"])
    assert cat == "jitter"
