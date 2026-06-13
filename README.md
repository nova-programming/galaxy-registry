# Galaxy Registry

The official package registry for the Nova programming language's Galaxy Package Manager.

A fully static, Git-backed registry — no database, no backend server. The website is hosted on Vercel and the registry data lives in this repository as JSON files under `packages/`.

## How it Works

1. **Browse** packages at [galaxy-registry.vercel.app](https://galaxy-registry.vercel.app)
2. **Install** with `galaxy install <pkg>`
3. **Publish** with `galaxy publish` (opens a GitHub Issue)

## Trust Tiers

- **Core** — maintained by the Nova team, ships with the compiler runtime
- **Verified** — human-reviewed for code quality and security
- **Community** — published via `galaxy publish`, anyone can contribute

## One-Command Install

```bash
curl -O https://galaxy-registry.vercel.app/install.py && python install.py
```

This installs both the Nova compiler and Galaxy package manager globally.

## Status

The Nova compiler is fully self-hosted (June 2026) — `nova.exe` successfully compiles itself. Supports x86_64 (primary) and ARM64 (secondary) backends. 190+ tests passing.

## Repository Structure

```
packages/          # Package JSON metadata files
  index.json       # Search index of all packages
  nova-math.json
  nova-http.json
  ...
admin.html         # Admin dashboard (login-gated)
documentation.html # Full language docs
templates.html     # Template system reference
install.py         # Unified installer (served by Vercel)
.github/workflows/ # PR validation, auto-quarantine, promotion queue
```
