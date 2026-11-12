# Galaxy Registry

The official package registry for the Nova programming language's Galaxy Package Manager.

A fully static, Git-backed registry — no database, no backend server. The website is hosted on Vercel and the registry data lives in this repository as JSON files under `packages/`.

## How it Works

1. **Browse** packages at [galaxy-registry.vercel.app](https://galaxy-registry.vercel.app)
2. **Install** with `galaxy install <pkg>`
3. **Publish** with `galaxy publish` (opens a pre-filled GitHub issue in the browser; nothing is uploaded directly)

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

The Nova compiler is fully self-hosted — `nova.exe` successfully compiles itself. The current release is v0.8.0, with x86_64 as the primary backend and ARM64 as a secondary backend. See the Nova repository for the current test and platform matrix.

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
.github/workflows/ # pr-validation, auto-quarantine, promotion-queue, sign-metadata
tools/             # build_package_pages.py, sign_registry.py
api/search.js      # search endpoint
versions/          # current compiler / galaxy version (0.8.0)
```

## Metadata signing

`tools/sign_registry.py` and the `sign-metadata` workflow can produce Ed25519 signatures (`packages/*.json.sig`).
As of this writing the Galaxy client has no trusted public key configured (`REGISTRY_PUBLIC_KEYS` in `nova/_galaxy.py` is
empty) and no `.sig` files are published, so installs are verified by content hash (`galaxy.lock`, SHA-256 where the
package metadata provides one) rather than by signature.
