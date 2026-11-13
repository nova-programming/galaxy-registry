# Galaxy Registry — Project Summary & Context

## Project Overview
- **Name**: Galaxy Registry (`galaxy-registry`)
- **Purpose**: Official package registry, interactive documentation portal, WebAssembly playground, and developer ecosystem for the Nova programming language.
- **Language surface the docs cover**: curly brace block syntax (`def foo(x) { ... }`), dotted module calls (`fs.read`, `path.join`, `text.trim`, `json.parse`), `for i in range(...)`, data constructors (`data Point { x: int, y: int }`), `d["k"]` / `"k" in d`, `\{` `\}` string escapes, inferred `-> string` returns, native Win32 GDI declarative GUI (`import gui`).
- **Signed metadata (dormant: no public key configured and no `.sig` files published yet)**: `tools/sign_registry.py` signs `packages/*.json` (Ed25519, `<file>.sig`); the `sign-metadata` workflow uses the `GALAXY_SIGNING_KEY` secret, and clients verify against `REGISTRY_PUBLIC_KEYS` in Nova's `_galaxy.py`.
- **Playground compiler source**: `nova_bundle.js` bundles the 18 compiler core and stdlib files directly into worker memory via `importScripts("nova_bundle.js")`, eliminating remote `raw.githubusercontent.com` network round-trips, CORS errors, adblocker blocks, and GitHub rate limits. `nova_worker.js?nova=<base-url>` can still load from a custom URL if specified.
- **Compiler Version**: Nova `v0.8.0` (see `versions/nova.json`) (Self-hosted systems programming language compiling to native x86_64/ARM64 machine code with small standalone binaries (simple CLI programs ~100-150 KB, GUI examples ~300 KB) and a double-buffered Win32 GDI GUI that targets 60 FPS (not measured) + NSS stylesheets).
- **Architecture**:
  - Fully static, Git-backed registry hosted on Vercel (`vercel.json`, `api/search.js`).
  - Zero server-side database; package submissions, reviews, and releases processed via GitHub Issues / PR workflows.
  - Data stored in `packages/*.json` and indexed by `packages/index.json`.
  - Frontend built with semantic HTML5, shared CSS design tokens (`theme.css`), and lightweight client scripts (`theme.js`).

## Universal Design & Theming Standards
- **Unified Dark & Light Themes (`theme.css`, `theme.js`)**:
  - Universal theme preference synchronization across all pages (`index.html`, `documentation.html`, `reference.html`, `examples.html`, `templates.html`, `playground.html`) via `localStorage.getItem('nova_theme')`.
  - Zero-FOUC initialization script executing immediately in `<head>`.
  - Instant theme toggle button in navigation bar (`&#9789;` / `&#9788;`), also updating Monaco Editor (`vs-dark` / `vs`).
- **Navigation**:
  - Shared top navbar: `Home` | `Quick Start` | `Packages` | `Docs` | `Reference` | `Examples` | `Templates` | `Playground` | `Theme Toggle` | `GitHub`.

## Pages & Structure
1. `index.html`:
   - **Hero Section**: Clear product positioning (Pythonic ergonomics, native machine code, small binaries, Win32 declarative GUI targeting 60 FPS).
   - **Primary CTA**: Prominent `⚡ Try Nova in Playground` button with glowing accent styling.
   - **Embedded Mini-Try-It Runner**: Live interactive snippet switcher (`Fibonacci`, `OOP Classes`, `Text Processing`) with instant output terminal.
   - **6 Feature Pillars Showcase**: Direct Native Binaries, Native Win32 GUI (targeting 60 FPS), Pythonic Static Typing, Nova Studio & Tooling, Git-Backed Package Registry, Cryptographic Provenance.
   - **Package Catalog (`view-libraries`)**: Full search with `/` keyboard focus, Tier tabs (`All`, `Core`, `Verified`, `Community`), and multi-mode sorting (`Upvotes`, `Name A-Z`, `Version`).
   - **Package Details (`view-package-details`)**: Dual install pills (`galaxy install`, `galaxy add`), Dependencies viewer with direct cross-linking, and Security & Provenance Card (Ed25519 signature verification, SHA-256 release checksums, static analysis, supply chain clean status).
2. `playground.html`:
   - Full Monaco Editor with real-time error squiggly markers from Pyodide WebAssembly worker.
   - **Capability Indicator Badge**: `🟢 Browser VM Sandbox` with clickable modal explaining Browser VM features vs Native toolchain requirements (`import gui`, C FFI, OS processes).
   - Categorized presets: *Beginner Basics*, *Data Structures*, *Algorithms*, *Standard Library*, *Native Showcase (Local Toolchain)*.
   - Shareable permalinks (`#code=...`), execution timing metrics, console copy/clear shortcuts (`Ctrl+K`, `Ctrl+Enter`).
3. `examples.html`:
   - 19 verified code examples, every single one featuring a dynamic **"▶ Run in Playground"** button that bridges directly into the playground.
   - **Interactive Coding Challenges**: 3 hands-on exercises (Prime Filter, Word Frequency Counter, Dictionary Inversion) with starter code, expandable hints, and verified solutions.
4. `documentation.html`:
   - Full language manual with floating "▶ Run in Playground" buttons injected on all runnable Nova code snippets.
5. `reference.html`:
   - Quick syntax cheat sheet and standard library functions with synchronized dark/light theming.
6. `templates.html`:
   - Visual scaffolding cards for *Pure Library*, *CLI Utility*, and *Desktop Native GUI App*.
   - **Live `galaxy.json` Manifest Builder**: Real-time form with live JSON preview and one-click copy.
   - Publishing checklist from project initialization to GitHub PR review.
7. `packages/`:
   - Package metadata JSON files (`nova-math.json`, `nova-http.json`, `nova-cli.json`, `nova-db.json`, `nova-img.json`, `index.json`) with declared dependencies and release checksums.

## Trust Tiers
1. **Core**: Inbuilt runtime packages maintained by the Nova core team (`nova-math`, etc.).
2. **Verified**: Community packages audited and human-reviewed for safety and code quality (`nova-http`, etc.).
3. **Community**: Openly published community packages with cryptographic SHA-256 release integrity.

## Nova Language Updates (Nov 2026)
- **Unified Memory System (`mem.*`)**:
  - Legacy `peek` and `poke` keywords are permanently deprecated and removed from the language.
  - Replaced by unified `mem.read_u8/u16/u32/u64` and `mem.write_u8/u16/u32/u64` memory intrinsics.
  - Zero-cost memory struct projection added: `mem.view(Type, addr)`.
- **Struct Default Field Values**:
  - `data` definitions now support default field expressions: `data Process { pid: int = 0, state: int = 1 }`.
  - Missing parameters in constructor calls (`Process()`, `Process(pid=10)`) automatically populate defaults.
- **Text-Based UI Widget IDs & Automatic Label Fallback**:
  - `ui.button(label, id="submit")` supports semantic text-based IDs and automatically defaults to hashing `label` when `id` is omitted.
  - `ui.clicked("submit")` tests clicks via 32-bit positive djb2 hashing (`uiHashId`), completely replacing numeric IDs.
- **Nova Service Framework (`stdlib/nsf.nv`)**:
  - Added standard library module `nsf` for IPC service calls to Nova OS services (`nsfCall`, `notifyShow`, `notifyDismiss`).
