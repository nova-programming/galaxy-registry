# Galaxy Registry — Project Summary & Context

## Project Overview
- **Name**: Galaxy Registry (`galaxy-registry`)
- **Purpose**: Official package registry and web portal for the Nova programming language's Galaxy Package Manager.
- **Language surface the docs cover**: dotted module calls (`fs.read`, `path.join`, `text.trim`, `json.parse`), `for i in range(...)`, data constructors (`Point(1, 2)`), `d["k"]` / `"k" in d`, `\{` `\}` string escapes, inferred `-> string` returns.
- **Signed metadata**: `tools/sign_registry.py` signs `packages/*.json` (Ed25519, `<file>.sig`); the `sign-metadata` workflow needs the `GALAXY_SIGNING_KEY` secret, and clients verify against `REGISTRY_PUBLIC_KEYS` in Nova's `_galaxy.py`.
- **Playground compiler source**: `nova_worker.js` loads the Python compiler from GitHub (`NOVA_REF`, default `main`; pin to a tag/commit to freeze). `nova_worker.js?nova=<base-url>` loads from a local checkout for testing.
- **Compiler Version**: Nova `v0.9.0` (Self-hosted systems programming language compiling to native x86_64/ARM64 machine code with double-buffered Win32 GDI GUI + NSS stylesheets).
- **Architecture**:
  - Fully static, Git-backed registry hosted on Vercel.
  - Data stored in `packages/*.json` and indexed by `packages/index.json`.
  - Zero server-side database; submissions and updates processed via GitHub Issues / PR workflows.
  - Frontend built with vanilla semantic HTML, CSS tokens, and JavaScript (with Marked.js and DOMPurify for secure markdown rendering).

## Pages & Structure
- `index.html`: Main landing portal and package catalog.
  - Views: `view-home` (Hero, tabbed install terminal, 4 architecture pillars), `view-getting-started` (Fast setup guide), `view-libraries` (Filterable package catalog with keyboard quick-focus via `/`), `view-package-details` (Deep package view with GitHub actions), `view-contribute` (Submission workflow).
- `documentation.html`: Full Nova language manual, compiler internals, stdlib reference, and syntax guides.
- `reference.html`: Language syntax cheat sheet and standard library function tables.
- `examples.html`: Interactive collection of runnable Nova code snippets.
- `templates.html`: Package scaffolding reference (`galaxy init library`).
- `playground.html`: In-browser Monaco editor and WebAssembly VM runner with curated presets (Fibonacci, FizzBuzz, Primes, Classes, Switch, Sort), theme toggling (Dark/Light), shareable permalink hashes (`#code=...`), and keyboard execution (`Ctrl + Enter`).
- `admin.html`: Maintainer management interface.
- `packages/`: Package metadata JSON files (`nova-math.json`, `nova-http.json`, etc.).

## Navigation & UI/UX Standards
- **Global Synchronized Top Navigation**:
  - Links: `Packages` | `Docs` | `Reference` | `Examples` | `Templates` | `Playground` | `GitHub`
  - Active states synchronized across all subpages.
- **Theme Integrity**:
  - Crisp, modern light-theme foundation (`Inter` for prose, `JetBrains Mono` for code/commands).
  - WCAG AA compliant contrast ratios, soft radial accents, and elevated cards.
  - Zero fake placeholder stats, artificial typewriter delays, or mock alert dialogues. Real, grounded engineering documentation.

## Trust Tiers
1. **Core**: Inbuilt runtime packages maintained by the Nova core team (`nova-math`, etc.).
2. **Verified**: Community packages audited and human-reviewed for safety and code quality (`nova-http`, etc.).
3. **Community**: Openly published community packages with cryptographic SHA-256 release integrity.
