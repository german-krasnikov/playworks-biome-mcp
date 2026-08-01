<div align="center">

<img src="./.github/assets/hero.svg" width="100%" alt="Luna MCP — AI-native debugger for Luna playable builds: a deep-space banner with a twinkling starfield, an orbiting moon, and the title Luna MCP"/>

<a href="https://github.com/german-krasnikov/playworks-biome-mcp">
<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=22&pause=900&color=39E0FF&center=true&vCenter=true&width=760&lines=Debug+Luna+builds+from+Claude.;Token-minimized+MCP+tools.;80-95%25+batch+token+savings.;Scene+.+Physics+.+Visual+.+Build." alt="Debug Luna builds from Claude — token-minimized MCP tools — 80-95% batch token savings">
</a>

</div>

<div align="center">

<sub>**STATUS**</sub><br>
<a href="./LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/german-krasnikov/playworks-biome-mcp?style=for-the-badge&labelColor=05060B&color=39E0FF&logo=opensourceinitiative&logoColor=white" /></a>
<img alt="GitHub stars" src="https://img.shields.io/github/stars/german-krasnikov/playworks-biome-mcp?style=for-the-badge&labelColor=05060B&color=39E0FF&logo=github&logoColor=white" />
<img alt="Last commit" src="https://img.shields.io/github/last-commit/german-krasnikov/playworks-biome-mcp?style=for-the-badge&labelColor=05060B&color=3FE0A3&logo=git&logoColor=white" />

<sub>**SPEC**</sub><br>
<img alt="Tests" src="https://img.shields.io/badge/tests-1620%20passing-3FE0A3?style=for-the-badge&labelColor=05060B" />
<img alt="Tools" src="https://img.shields.io/badge/tools-198-39E0FF?style=for-the-badge&labelColor=05060B" />
<img alt="Status" src="https://img.shields.io/badge/Status-Beta%20v0.1.0-FFC24B?style=for-the-badge&labelColor=05060B" />

<sub>**STACK**</sub><br>
<img alt="Python" src="https://img.shields.io/badge/Python-3.10+-8B7DFF?style=for-the-badge&labelColor=05060B&logo=python&logoColor=white" />
<img alt="MCP" src="https://img.shields.io/badge/MCP-compatible-8B7DFF?style=for-the-badge&labelColor=05060B&logo=anthropic&logoColor=white" />
<img alt="CDP" src="https://img.shields.io/badge/CDP-Chrome%20DevTools-0FA3C7?style=for-the-badge&labelColor=05060B&logo=googlechrome&logoColor=white" />

</div>

> **MCP server bridging your AI coding assistant to Luna playable-ad builds running in Chrome** — over the Chrome DevTools Protocol. Token minimization is the soul of the project.

<sub>Works with</sub> <kbd>Claude Code</kbd> <kbd>OpenAI Codex CLI</kbd> <kbd>Cursor</kbd> <kbd>Windsurf</kbd> <kbd>any stdio MCP client</kbd>

<img src="./.github/assets/divider.svg" width="100%" alt="" />

## Why Luna MCP?

- **Stop burning tokens on boilerplate.** Each `batch` call replaces 5–20 individual MCP round-trips — **80–95% fewer tokens** on the same work.
- **Stop copy-pasting from Chrome DevTools.** Your assistant inspects the live Luna scene, edits runtime properties, captures screenshots, and triages console errors — all over CDP, without leaving the chat.
- **Stop guessing what broke.** 4-tier build diffing, physics backend detection, visual regression, and smart error triage — structured answers, not raw log dumps.

**Before / after — diagnosing a Luna playable build:**

```
Before: 5 separate MCP calls (~1500 tokens overhead)

get_hierarchy depth=2
get_component path="Canvas/EndCard" component_type="Image"
diagnose_object path="Canvas/EndCard"
screenshot
get_console level=E count=10
```

```
After: 1 batch call (~200 tokens, 87% savings)

batch("
  get_hierarchy depth=2
  get_component path=Canvas/EndCard component_type=Image
  diagnose_object path=Canvas/EndCard
  screenshot
  get_console level=E count=10
")
```

<img src="./.github/assets/divider.svg" width="100%" alt="" />

## Quick Start

**Prerequisites:** <kbd>Python 3.10+</kbd> · <kbd>Chrome</kbd> · <kbd>Claude Code / Codex CLI / any MCP client</kbd>

**1. Install the server**

```bash
git clone https://github.com/german-krasnikov/playworks-biome-mcp.git
cd playworks-biome-mcp/server && pip install -e ".[dev]"
```

**2. Launch Chrome with CDP**

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 --user-data-dir=/tmp/luna-debug-profile

# Linux
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/luna-debug-profile
```

Open your Luna build URL in that Chrome window.

**3. Wire it up**

Add to `.mcp.json` (Claude Code) or `.codex/config.toml` (Codex CLI):

```json
{
  "mcpServers": {
    "playworks-biome-mcp": {
      "type": "stdio",
      "command": "python3",
      "args": ["-m", "luna_mcp.server"],
      "cwd": "/absolute/path/to/playworks-biome-mcp/server",
      "env": { "PYTHONPATH": "src" }
    }
  }
}
```

Restart your client. Ask: *"Inspect the Luna scene hierarchy"* — done.

<details>
<summary><b>Troubleshooting</b></summary>

- **"No Luna page found"** — Confirm Chrome launched with `--remote-debugging-port=9222`. Check `lsof -i :9222`.
- **Multiple tabs open** — Set `LUNA_PAGE_FILTER=my-build` to target the right tab.
- **Server doesn't appear** — Verify `cwd` points to `server/`, not the repo root. Restart your client.
- **Blank screenshots** — Luna page must be visible (not minimized). Try `--disable-gpu`.

</details>

<img src="./.github/assets/divider.svg" width="100%" alt="" />

## Features

<img src="./.github/assets/features-divider.svg" width="100%" alt="" />

- 💸 **Token Economy** — `batch` compresses 5–20 calls into one (80%+ savings), JPEG screenshots (3–5×), Set-of-Mark (70–90%), server-side Haiku sampling (~28k saved/shot)
- 🔎 **Scene Inspection** — hierarchy, components, objects by name/type, transpiled C# back-mapping
- ✍️ **Runtime Editing** — mutate properties live via CDP eval, post-flight reflection confirms changes
- 📸 **Visual Analysis** — screenshots, text summaries (30–100× lighter), baseline regression, SoM annotations
- 🧬 **Build Diffing** — 4-tier (file/semantic/visual/auto) with `log(N)` bisect to find the culprit
- 🪐 **Physics Forensics** — Goblin/Verlet/Baked/Unified backend detection, symptom classification, knowledge base
- 🚨 **Error Triage** — console streaming + smart domain routing (build/runtime/physics/Playworks)
- ⚡ **Performance** — frame-time breakdown, GPU/VRAM/startup probes, heap sampling, JS coverage
- 🚩 **Flag Discovery** — scan Jakefile for hidden flags, persistent catalog, intent-matched recommendations
- 🤖 **Macros & Batch** — intent→plan→validate→execute, domain-scoped macros (endcard/gameplay/monetization)
- 🛰️ **CDP Domains** — CPU throttle, device emulation, network conditions, gesture simulation, step frame

<img src="./.github/assets/divider.svg" width="100%" alt="" />

## Recent Changes

<div align="center">
  <img src="./.github/assets/changelog.svg" width="900" alt="Animated release timeline" />

<a href="https://german-krasnikov.github.io/playworks-biome-mcp/changelog/"><img alt="Explore the interactive Flight Log" src="https://img.shields.io/badge/Explore_Interactive_Flight_Log-39E0FF?style=for-the-badge&logo=github&logoColor=05060B&labelColor=0E1120"></a>

<sub>See <a href="./CHANGELOG.md"><b>CHANGELOG.md</b></a> for full history</sub>

</div>

<img src="./.github/assets/divider.svg" width="100%" alt="" />

> [!IMPORTANT]
> **Unofficial community tool.** Luna MCP is an independent, community-built project. **Luna** is a product of **Luna Labs**. This project is **not affiliated with, endorsed by, or sponsored by Luna Labs.**

<div align="center">

<sub>MIT License · © <a href="https://github.com/german-krasnikov">German Krasnikov</a> · <a href="https://github.com/german-krasnikov/playworks-biome-mcp">⭐ Star</a></sub>

<img src="./.github/assets/footer-wave.svg" width="100%" alt="" />

</div>
