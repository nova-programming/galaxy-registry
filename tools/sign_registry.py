#!/usr/bin/env python3
"""Sign registry metadata with Ed25519 so `galaxy install` can verify it.

For every packages/*.json (including index.json) this writes packages/<file>.json.sig, the base64
Ed25519 signature of the exact file bytes.

The private seed comes from the GALAXY_SIGNING_KEY environment variable (64 hex characters, the
"private seed" printed by `galaxy keygen`). Without it the script does nothing and exits 0, so
forks and pull-request builds are not broken.

Usage: python tools/sign_registry.py [packages_dir]
"""
import base64
import os
import sys


def main():
    seed_hex = os.environ.get("GALAXY_SIGNING_KEY", "").strip()
    folder = sys.argv[1] if len(sys.argv) > 1 else "packages"
    if not seed_hex:
        print("GALAXY_SIGNING_KEY is not set; skipping signing.")
        return 0
    try:
        seed = bytes.fromhex(seed_hex)
    except ValueError:
        print("GALAXY_SIGNING_KEY must be hex.", file=sys.stderr)
        return 1
    if len(seed) != 32:
        print("GALAXY_SIGNING_KEY must be a 32-byte (64 hex character) seed.", file=sys.stderr)
        return 1

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.from_private_bytes(seed)
    public = key.public_key()
    changed = 0
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(folder, name)
        with open(path, "rb") as f:
            raw = f.read()
        signature = key.sign(raw)
        public.verify(signature, raw)  # sanity check before publishing
        encoded = base64.b64encode(signature).decode("ascii") + "\n"
        sig_path = path + ".sig"
        old = open(sig_path, encoding="ascii").read() if os.path.exists(sig_path) else None
        if old != encoded:
            with open(sig_path, "w", encoding="ascii", newline="\n") as f:
                f.write(encoded)
            changed += 1
    print(f"Signed {changed} file(s) in {folder}/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
