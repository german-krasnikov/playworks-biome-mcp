"""4 starter flag entries for FlagCatalog (compressTexturesWebP removed — UNVERIFIED)."""
from .catalog import FlagCatalog, FlagEntry

SEED_FLAGS = [
    FlagEntry(
        name="disableMinify",
        description="Disable JS minification",
        enables="readable function/variable names in console and stack traces",
        side_effects=["build size 2x bigger", "fps unchanged"],
        build_size_delta_pct=100.0,
        perf_delta="0%",
        risk="low",
        confidence=0.9,
        source="seed",
    ),
    FlagEntry(
        name="forceUncompressedTextures",
        description="Disable PNG/JPEG compression for textures",
        enables="full quality textures, easy texture inspection",
        side_effects=["build +30%", "GPU memory 2x"],
        build_size_delta_pct=30.0,
        perf_delta="-15% fps in low-mem devices",
        risk="medium",
        confidence=0.85,
        source="seed",
    ),
    FlagEntry(
        name="useUnstableSolver",
        description="Use experimental physics solver",
        enables="1.5x physics performance",
        side_effects=["cloth/rope jitter", "may fail on edge cases"],
        build_size_delta_pct=0.0,
        perf_delta="+50% physics",
        risk="high",
        confidence=0.7,
        source="seed",
    ),
    FlagEntry(
        name="enableConsoleLogging",
        description="Enable verbose runtime console logging",
        enables="detailed Luna runtime trace events",
        side_effects=["log spam in console", "minor perf overhead"],
        build_size_delta_pct=2.0,
        perf_delta="-2% fps",
        risk="low",
        confidence=0.95,
        source="seed",
    ),
]


def seed_default(catalog: FlagCatalog) -> int:
    """Add seed entries if absent. Returns count added."""
    n = 0
    for s in SEED_FLAGS:
        if catalog.get(s.name) is None:
            catalog.add(s)
            n += 1
    if n:
        catalog.save()
    return n
