# Galaxy — Technical Claims Correction Log (Phase 0)

Record of claims corrected on the Galaxy website, with the evidence from the Nova codebase that
motivated each change. No performance numbers were invented; where a claim couldn't be backed by
a real measurement, it was softened to describe intent/design target instead of a result.

| File:line (before edit) | Old claim | Why it was wrong | New wording | Evidence |
|---|---|---|---|---|
| `examples.html:484,487-489,504` | "Cryptographically secure random numbers via ChaCha20 PRNG" | `runtime.c` implements plain xorshift64, not the ChaCha20 cipher; `reference.html` itself already called `chacha20_init` a "compat name" seeding xorshift | Describes it as a seedable xorshift64 generator; explicitly states it is NOT cryptographically secure | `nova/runtime.c` `_chacha20_init`/`_rng_next` (xorshift64, not ChaCha20) |
| `index.html:501` | "C-speed native machine code (<250KB binaries)" | Nova's own `docs/optimization_plan.md` benchmarks show ~2.2-2.5x slower than `gcc -O2` on fib(38); binary size varies widely by program | "native x86_64/ARM64 machine code compilation" (speed claim dropped); binary-size claim moved to the pillar card with a qualified range | `nova/docs/optimization_plan.md` |
| `index.html:567` | "sub-250KB executables and zero C-runtime dependency" | Compiled GUI example binaries in the repo measure 299KB-328KB — over the stated limit | "Simple CLI programs typically compile under 150KB; GUI applications are typically under 300KB" | Measured `.exe` sizes in `nova/examples/*.exe` |
| `index.html:571` | "Native 60 FPS Win32 GUI" (stated as achieved) | No test in the repo measures actual achieved FPS; frame-pacing code targets 60 FPS as a design goal, not a verified result | "Native Win32 GUI, Targeting 60 FPS" | `nova/tests/test_framebuffer.py`, `test_sandbox.py`, `test_studio.py` test lifecycle/correctness only, not FPS |
| `index.html:577` | "Hindley-Milner static type inference, algebraic data types, pattern matching" | No Hindley-Milner unification algorithm exists anywhere in the codebase (zero matches for "Hindley"/"Milner"); Nova's `switch` is value-equality branching, not structural pattern matching; "algebraic data types" overstates Nova's plain `enum` support | "static type inference and enums" | `nova/stdlib/type_checker.nv`, `nova/bootstrap/compiler/type_checker.py` (no HM unification); `nova/stdlib/parser.nv:1810-1993` (`EnumDef`, not full ADTs/pattern matching) |
| `index.html:581-582` | "Nova Studio IDE, integrated Particle Sandbox, Nova LSP" | "Nova Studio" is a demo/benchmark app (`nova/examples/nova_studio.nv`), not a separate IDE product; "Particle Sandbox" is similarly a demo example, not a shipped tool | "Self-Hosted Toolchain" — self-hosted compiler, LSP, `nova run/build` (drops the IDE/Sandbox product framing) | `nova/docs/AGENT_LOG.md`, `nova/tests/test_studio.py` (confirms demo-app framing) |
| `index.html:592` | "Ed25519 ... SHA-256 ... guarantee tamper-proof package distribution and supply chain security" | `GALAXY_ALLOW_UNVERIFIED=1` is a documented, explicit bypass of verification — "guarantee"/"tamper-proof" overclaims a mechanism that can be turned off | "verified by default on install. Verification can be disabled for local development via an explicit opt-out flag" | `nova/_galaxy.py` (`GALAXY_ALLOW_UNVERIFIED`), `nova/AGENTS.md` |
| `playground.html:453-457` | "Hindley-Milner Type Inference", "Functions, Lambdas & Closures", "Pattern Matching & Switch Blocks" | Same HM issue as above; closures are confirmed absent anywhere in the codebase (no `Closure` AST node, no captured-variable codegen in either backend); same pattern-matching overstatement | "Static Type Inference", "Functions & Named Function Calls", "Switch/Case & Enum Blocks" | Grep across all 8 codegen files for closure/capture machinery returned zero matches |
| `playground.html:472` | "Sub-250KB Standalone Machine Binaries" | Same binary-size issue as `index.html:567` | "Small Standalone Machine Binaries (~100-300KB)" | Same evidence as above |
| `playground.html:368` | "Switch Pattern Matching" (dropdown label) | Same pattern-matching overstatement | "Switch / Case Statement" | Same evidence as above |
| `documentation.html:257` | "native x86_64 and ARM64 targets" (presented as equal) | Nova's own `README.md` calls x86_64 "primary backend, fully verified" and ARM64 "secondary backend" | Added "(the primary, fully-verified backend)" / "(a secondary backend)" qualifiers | `nova/README.md:188` |
| `documentation.html:863` | "Call Nova's C-speed functions natively from Python" | Same C-speed issue as above | "Call Nova's compiled native functions from Python" | Same evidence as `index.html:501` |
| `templates.html:295` | "60 FPS double-buffered Win32 GDI desktop app" (stated as achieved) | Same 60 FPS issue as above | "Double-buffered Win32 GDI desktop app, targeting 60 FPS" | Same evidence as `index.html:571` |
| `playground.html:687,698,702` | "runs natively with 60 FPS", "60 FPS double-buffered ... graphics" (code-sample comments/strings) | Same 60 FPS issue | Reworded to "targeting a 60 FPS frame budget" / "Double-buffered Win32 desktop graphics" | Same evidence |

**Not changed** (verified accurate, kept as-is): "Self-hosted" / "Nova compiles itself" claims
(strongly supported by the Stage1→Stage2→Stage3 SHA-256-verified self-host pipeline in
`nova/tools/run_selfhost_gate.py` and `nova/docs/AGENT_LOG.md`); the "free/close guaranteed on
return" defer-style cleanup claims in `documentation.html`/`reference.html` (a real, deterministic
language feature, not a security/performance claim); the existing benchmarking disclaimer already
present at `documentation.html:929-930`.
