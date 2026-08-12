# Changelog

All notable changes to **Playworks Biome MCP** (`playworks-biome-mcp`) are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Playworks Biome MCP is a token-minimal MCP server that lets an AI coding assistant debug
Luna (a Unity-to-JS transpiler) playable-ad builds running in Chrome over the
Chrome DevTools Protocol (CDP).

---

## [v0.2.0] — 2026-08-12

### Added
- CI infrastructure: ruff lint gate, test matrix (Python 3.10–3.13), coverage (90%), codecov
- `codecov.yml` with auto target and 1% threshold
- `dependabot.yml` for weekly dependency and monthly GHA updates
- `__version__` via `importlib.metadata` for programmatic version access
- `pyproject.toml`: ruff config (E/F/I/C4), coverage config, strict markers, timeout

### Changed
- Renamed package from `luna-kiss-mcp` to `playworks-biome-mcp`
- Data directory moved from `~/.luna_mcp` to `~/.playworks-biome-mcp` (auto-migration on first start)
- FastMCP display name updated to `PlayworksBiomeMCP`
- Shadow git identity updated to `playworks-biome@local`
- CLI help text updated to Playworks Biome branding
- Import sorting enforced across all source and test files
- `templates/registry.py` uses `data_dir()` instead of hardcoded path

### Fixed
- Broken `EXPOSED_TOOLS` import in test_consolidation.py (moved to wiring.py)
- Unclosed file handles in test_asset_tools.py (ResourceWarning)

---

## [0.1.0] - Beta

First public Beta. **112 AI-exposed tools** + **37 batch-only** = **149 total tools**,
**1936 tests** across **147 test files**, **~23,779 LOC** of server code. Python ≥ 3.10
(3.10 / 3.11 / 3.12 / 3.13). JS helpers (`luna_helpers.js` v1.6.1, 2295+ LOC) injected
into the Luna iframe and re-injected on reconnect.

### Highlights

- **Token Economy** — the soul of the project. Multiple stacked strategies cut LLM cost:
  - `batch` runs multi-step workflows in a single round-trip (**80%+** token savings).
  - Visual Tier 1 returns text summaries instead of PNG (**30–100×** savings).
  - JPEG screenshots (**3–5×** vs PNG).
  - Set-of-Mark annotated screenshots (**70–90%** savings on interactive flows).
  - Cost Budget Router smart routing (**up to 92%** savings).
  - Plain-text (not JSON) responses, plus server-side LLM sampling via a Haiku
    subprocess that saves **~28k tokens** on screenshots.
- **Eight capability pillars** — scene inspection, runtime property editing,
  screenshots + visual analysis/regression, 4-tier build diffing
  (file / semantic / visual / auto), feature-flag exploration, physics diagnostics
  (Goblin / Verlet / Baked / Unified backends), console + error monitoring/triage,
  and performance metrics (frame time, draw calls, memory, GPU / VRAM / startup).
- **6-layer composition stack** (outermost-first):
  Recorder → Hinter → Degradation → Budget gate → Reflect → Schema guard.
- **Lazy architecture** — auto-connects on the first tool call; no cache, because
  Luna scene state changes too fast to trust one.
- **Works with any stdio MCP client** — Claude Code, OpenAI Codex CLI, Cursor,
  Windsurf, and more.

### Documentation

- Replaced the plain-text Flight Log milestone table with a self-contained
  animated release-timeline SVG (`.github/assets/changelog.svg`): the five
  milestones reveal in sequence along a glowing vertical spine as a marker
  descends. Visible-at-rest and theme-safe (works on light and dark); the
  text table is preserved in a collapsed panel for accessibility.
- Redesigned the README into a sectioned animated landing page: hero banner,
  Token Economy, Philosophy, Capabilities, First Steps, Demo, Architecture,
  Tool Arsenal, The Crew, Ecosystem, and a Flight Log release timeline.
- Added 16 self-contained animated SVG assets under `.github/assets` (hero,
  dividers, token-savings, composition stack, architecture flow, terminal, crew,
  ecosystem, timeline, footer).
- Added a new Tool Arsenal section with a headline ten-tool table plus a full
  catalog grouped by category (Scene, Visual, Physics, Build & Assets, Flags,
  Performance, Diagnostics, Macros & Batch, CDP Domains) in collapsible panels.
- Reorganized setup, per-client config (Claude Code / Codex CLI / others),
  environment variables, and troubleshooting into collapsible sections while
  preserving all prior content; added a three-step First Steps quickstart.
- Added a Crew roster documenting the human captain and five model-backed AI
  agents (senior-architect, senior-developer, code-reviewer, doc-keeper,
  luna-debugger) with the pipeline flow.
- Added a CHANGELOG.md in Keep a Changelog format and linked it from the README
  release timeline.

---

## Sprints 1–6 - Probes, CDP domains, and CI

Depth and field-readiness for live debugging.

### Added

- **Sprint 1 — Token economics + probes:** JPEG screenshots, frame-time breakdown,
  and native perf probes feeding richer performance metrics.
- **Sprint 2 — Diagnostics depth:** animator graph dump, INSIGHTS state/events,
  tween inventory + health checks, and enriched text diagnostics.
- **Sprint 3 — Interaction + lifecycle:** synthetic gestures via CDP Input
  (swipe / click), DOTween control, lifecycle waiter + event stream, and physics
  forensics (`inspect_bodies`, `physics_query`).
- **Sprint 4 — Native CDP domains:** emulation (CPU throttle, device metrics),
  network conditions + URL blocking, heap sampling, frame tracing, and a JS
  coverage map reconciled back to C#.
- **Sprint 5 — Static / docs intelligence:** a C# linter (`lint_csharp`,
  `audit_required_apis`), Jake task discovery, and Luna build-issue seeds.
- **Sprint 6 — Server health + advanced:** budget-calibrator wiring, a headless
  CI harness with JUnit XML output, playground field control, and GPU / VRAM /
  startup probes plus `step_frame` execution.

---

## Waves 1–6 - Intelligence layers

The brain of the server: learning, prediction, and server-side AI.

### Added

- **Wave 1:** EventBus (push-based events), Action Templates (pre-compiled batch
  shortcuts), and Visual Regression v2 (two-tier pixel → semantic diff).
- **Wave 2:** MetricsRegistry (per-tool p50/p95), a SQLite LessonStore, a
  Speculator with auto-disable prefetch, a post-write Watchdog, and Macro-tools
  (`do`, `ask`, `endcard`, `gameplay`, `monetization`).
- **Wave 3:** Typemap-aware cross-build lessons, Multi-Frame Visual analysis,
  and the ToolHinter + Graceful Degradation safety net.
- **Wave 4:** Budget Auto-tuning (adaptive cap from historical data) and Playable
  Replay (record/replay MCP sessions with redaction).
- **Wave 5:** Physics Detective — Goblin / Verlet / Baked / Unified backend
  detection, symptom classification, and physics knowledge seeds.
- **Wave 6:** SamplingService brain features F11–F20 — Smart Error Triage,
  Compliance Checker, Intent Router, Transpiled Code Explainer, Hierarchy
  Distiller, Auto-Playtest generation, and a Runtime Anomaly Detector.

---

## Phase A+B+C - Foundation

### Added

- Initial refactor and audit pass establishing the core architecture:
  AI Assistant ↔ (stdio) ↔ Playworks Biome MCP (Python, FastMCP) ↔ (CDP WebSocket) ↔ Chrome.
- CDP bridge with auto-reconnect, JS helper injection into the Luna iframe,
  JS→C# source mapping, and the Playworks typemap resolver.
- Engineering guardrails: SOLID / DRY / KISS / TDD (Red-Green-Refactor),
  files < 200 lines, functions < 50 lines, and no speculative abstractions.

---

[0.1.0]: https://github.com/german-krasnikov/playworks-biome-mcp/releases/tag/v0.1.0
