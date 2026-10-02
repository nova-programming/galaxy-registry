# Nova Programming Language

A language that bridges high-level Pythonic simplicity with low-level C-like control. Nova features a **fully functional self-hosted compiler pipeline** — the compiler is written in Nova itself, can lex, parse, and generate x86 assembly, and bootstraps via GCC to produce native executables.

## Quick Install

One command, zero dependencies — installers handle everything including GCC/MinGW bundling on Windows:

**macOS / Linux (bash, pre-installed):**
```bash
curl -O https://galaxy-registry.vercel.app/install.sh && bash install.sh
```

**Windows (PowerShell, pre-installed):**
```powershell
Invoke-WebRequest -Uri https://galaxy-registry.vercel.app/install.ps1 -OutFile install.ps1; powershell -File install.ps1
```

**Python fallback (any platform):**
```bash
curl -O https://galaxy-registry.vercel.app/install.py && python install.py
```

After installation, open a **new** terminal, then:

```bash
nova --version           # Check Nova version
nova build hello.nv      # Compile a Nova program (requires GCC)
nova run hello.nv        # Compile, link, and immediately execute
nova check hello.nv      # Parse and type-check without building
nova lint hello.nv       # Show advisory style warnings; does not rewrite files
nova lint --strict hello.nv  # Treat advisory warnings as failures
nova fmt hello.nv        # Check deterministic formatting
nova fmt --write hello.nv  # Apply formatting explicitly
nova dev hello.nv        # Run in VM mode (no GCC needed)
```

## Portable standard library

The standard library is a set of small modules. `import` one, then call its
functions with a dot: `fs.read(p)`, `path.join("a", "b")`, `text.trim(s)`.
Each call compiles to a plain function call, so there is no runtime cost, and
the older flat spellings (`fs_read`, `path_join2`, ...) keep working.

```nova
import path
import fs
import text
import time

name = path.base(path.join("tmp", "notes.txt"))
if fs.exists("notes.txt") {
    print(text.trim(fs.read("notes.txt")))
}
fs.makeDir("data")
fs.write("data/notes.txt", "Nova is simple and fast.
")
fs.copy("data/notes.txt", "data/notes.backup.txt")
print(time.ticks())
```

| Module | Functions |
|---|---|
| `fs` | `exists size kind makeDir delete copy move read write` |
| `path` | `join` (any number of parts, or one list), `base dir ext` |
| `env` | `get set args platform` |
| `process` | `run shell exit` |
| `time` | `now ticks` |
| `json` | `stringify` |
| `text` | `toInt trim startsWith endsWith indexOf contains replace split join repeat upper lower words lines padLeft padRight count capitalize` |

Members use camelCase (`makeDir`, `startsWith`, `.asList`, `.valueByte`).
`nova lint` flags old spellings (`STYLE003`) and
`nova fmt --write --modernize file.nv` rewrites them for you.
`read`, `write`, `close`, `api`, `openf` and `data` are only keywords where
they are used as built-ins or declarations, so they are fine as variable names.

These modules are backed by the existing
cross-platform runtime boundary. Filesystem helpers return simple status/value
results instead of hiding operational failures. `process_shell` is explicitly
named because it invokes a shell. `json_stringify(value)` is available from
the `json` module for compact serialization; JSON parsing remains pending
until recursive VM/native conversion is complete.
`env_get(name)` returns `""` when an environment variable is absent.
`env_set(name, value)` updates the current process environment and returns
`1` on success or `0` on failure.
`fs_copy` overwrites an existing destination, `fs_move` replaces an existing
destination where the platform supports it, and `fs_delete` removes files
only; all three return `1` on success or `0` on failure.
`process_run(["program", "argument"])` executes without a shell and returns
the child exit code, or `-1` when the process cannot be launched.

## Galaxy package manager

```bash
galaxy --version         # Check Galaxy version
galaxy init my-lib       # Create a library
galaxy install pkg       # Install a package
galaxy verify            # Check installed packages against galaxy.lock (content hashes)
galaxy keygen            # (maintainers) create an Ed25519 key to sign registry metadata
```

Registry metadata can be signed (Ed25519): `packages/*.json.sig` is checked against the keys in `REGISTRY_PUBLIC_KEYS` (`_galaxy.py`) or `GALAXY_REGISTRY_KEYS`. With keys configured, missing or invalid signatures stop the install; `GALAXY_ALLOW_UNSIGNED=1` overrides and `GALAXY_REQUIRE_SIGNATURE=1` enforces even without configured keys. Installed packages are also pinned by content hash in `galaxy.lock` (`galaxy verify`).

**To use `nova` and `galaxy` immediately without restarting your terminal:**

- **cmd.exe:** `call "%LOCALAPPDATA%\nova\use_nova.bat"`
- **PowerShell:** `$env:PATH = "$env:LOCALAPPDATA\nova;$env:PATH"`

Stay updated with:

```bash
nova update              # Update Nova compiler
galaxy update            # Update Galaxy CLI
galaxy upgrade [pkg]     # Update installed packages
```

Remove Nova entirely:

```bash
python install.py --uninstall   # Remove Nova, Galaxy, and PATH entries
```

## Usage

### Primary — `nova` commands (self-hosted bootstrap)

```bash
# Build to native executable (uses the self-hosted compiler; GCC-free when the internal linker supports the target)
nova.exe build program.nv

# Compile, link, and immediately execute (args after the file are forwarded)
nova.exe run program.nv arg1 arg2

# Assemble .s file and link directly
nova.exe assemble-link input.s output.exe

# Build to bare-metal flat binary (no PE headers, no imports)
nova.exe build-bare program.nv 31744 _start
nova.exe assemble-bare program.s output.bin 0x7C00
```

### Fallback — `python` commands (Python bootstrap)

If the self-hosted compiler (`nova.exe`) is not available or encounters issues, use the Python compiler directly:

```bash
# Build to native executable (uses GCC as linker)
python main.py build program.nv

# Run in the Python bytecode VM (fast iteration, no GCC needed)
python main.py dev program.nv
```

## Python Bridge (Seamless Interop)

Nova features a zero-friction Python Bridge (`nova_py.py`) that allows you to natively import `.nv` files directly into Python scripts. The bridge automatically compiles the Nova code into high-speed native assembly (`.dll`/`.so`), handles SysV ABI translations, maps C-types to Python types, and binds the functions—all transparently on import.

To use it, just import `nova_py` once, then import your Nova modules as if they were standard Python modules:

```python
import nova_py
import math_lib # Automatically compiles math_lib.nv and loads it natively!

# Call Nova's C-speed functions natively from Python
result = math_lib.calculate_fibonacci(40)
print(result)
```

## Self-Hosted Bootstrap Chain

The compiler is written in Nova and bootstraps in three stages:

1. **Stage 0** — Python compiler (`main.py`) compiles `nova.nv` → `nova.s` → GCC → `nova.exe`
2. **Stage 1** — `nova.exe` (self-hosted compiler) compiles `nova.nv` → `nova.s` → executable. Windows targets can use the internal assembler/linker; Unix targets currently use GCC for final linking.
3. **Stage 2** — The Nova-compiled executable can now recompile itself, proving the bootstrap is self-sustaining

The compiler pipeline within a single invocation:

```
.nv source → lexer.nv → parser.nv → type_checker.nv → backend/<arch>/codegen.nv → assembler.nv → linker.nv → .exe
```

Supported architectures:
- **x86_64** — primary target, fully verified self-hosted bootstrap
- **ARM64** — secondary target, codegen implemented (CI-tested on macOS)

Additional standard library modules:
- `types.nv` — Type system abstraction (scalar, struct, list, func types)
- `type_checker.nv` — Static type inference and enforcement
- `errors.nv` — Structured error/warning printer with fix suggestions
- `assembler.nv` — target-specific instruction encoder (assembles supported .s text into byte streams)
- `linker.nv` — Windows PE executable generator (packages bytes into .exe directly, integrated)
- `slice.nv`, `ffi.nv`, `fs.nv`, `path.nv`, `env.nv`, `process.nv`, `time.nv`, `json.nv` — portable standard-library modules

## Project Structure

```
nova/
├── nova.nv           # Self-hosted compiler entry point / CLI driver
├── runtime.c         # C runtime wrappers for native compilation
├── _galaxy.py        # Galaxy package manager (also exposed as galaxy/ and tools/galaxy.py)
├── install.py|.sh|.ps1  # Installers
├── bootstrap/        # Python bootstrap compiler (Stage 0) and VM
│   ├── main.py           # Bootstrap CLI entry point
│   ├── lexer/ parser/ nova_ast/ modules/   # Front end
│   ├── compiler/         # Type checker + x86_64/ARM64 codegen backends
│   └── vm/               # Bytecode compiler and VM (`nova dev`)
├── stdlib/           # Self-hosted compiler and standard library, written in Nova
│   ├── lexer.nv parser.nv type_checker.nv types.nv compiler.nv
│   ├── codegen_common.nv peephole.nv errors.nv vm.nv
│   ├── backend/x86_64/   # codegen*.nv, assembler*.nv, linker.nv, os_windows.nv, os_unix.nv
│   ├── backend/arm64/    # same layout for ARM64
│   ├── fs.nv path.nv env.nv process.nv time.nv json.nv slice.nv ffi.nv system.nv
│   └── gui.nv nss.nv     # Win32 GDI GUI toolkit and NSS stylesheets
├── tools/            # nova_py (Python bridge), libtest, galaxy wrapper
├── docs/             # Language features, internals, libraries
├── examples/         # GUI and UI demos
└── tests/            # Python tests and .nv fixtures (run with `python -m pytest`)
```

## Language Features

- **Static type inference** — full type checking with `int`, `float`, `bool`, `string`, `byte`, `void`, `list[T]`, struct types
- **Array bounds checking** — runtime bounds checks on all list/array access, safe termination on out-of-bounds
- **List type unification** — `[1, 2, 3]` infers `list[int]`; heterogenous lists rejected at compile time
- **Compile-time constant folding** — `1 + 2 * 3` evaluates to `7` at compile time, emits single `push 7`
- **Capacity-based list allocation** — `append` doubles capacity exponentially, no realloc on every insertion
- **Float literals + x87 runtime** — `x = 3.14; print(x)` uses IEEE 754 single precision, x87 FPU for arithmetic
- **For-in loops `for i in items { ... }`** — iterate over list elements directly
- **`for i in range(n)` / `range(a, b)` / `range(a, b, step)`** — Python-style counting loops (end excluded, step is a literal); compiled to the same counted loop as `for i = a to b step s`, so bounds-check elimination still applies
- **Data constructors** — `Point(1, 2)` or `Point(x=1, y=2)` build a `data` value (missing fields are zero); `Point()` and field assignment still work
- **Dictionary shortcuts** — `d["k"]`, `d["k"] = v`, `"k" in d`, `"k" not in d` (`in` is for dictionaries; use `text.contains` for strings)
- **Return types are inferred** — `def label(n) { return "n=" + str(n) }` prints as a string without a `-> string` annotation when every known return is a string
- **`json.parse(text)`** — parse JSON into a typed tree (`json.get`, `json.at`, `json.asInt`, `json.asString`, ...); see `stdlib/json.nv`
- **Boolean short-circuit** — `and`/`or` skip right operand evaluation when left determines the result
- **Debug prints (`printd`)** — `printd(x)` outputs `debug - [line N]: <value>` with automatic line number, enabled via `--debug` flag
- **Smart error messages** — compiler errors include error category, line number, and fix suggestions
- Variables and expressions (inferred typing)
- Mutable by default; `const` for immutability
- Functions with typed parameters and return types
- While & For loops (with `to`, `downto`, `step`)
- If-elif-else conditionals
- `break` / `continue`
- Logical operators (`and`, `or`, `not`)
- Bitwise operators (`&`, `<<`, `>>`)
- Data structs with `has` field-existence check
- String slicing `s[i:j]`
- String escape sequences
- Raw memory blocks (`@raw`) with `alloc`/`free`
- Data structures (`data` blocks)
- FFI to C libraries
- Module import system (circular-import-safe)
- Bare-metal flat binary output (`build-bare` / `assemble-bare`, no PE headers)
- `@raw` block assembly passthrough (lines starting with x86 mnemonics emit raw assembly; others compile as normal Nova)
- `@export { name1, name2 }` inside `@raw` blocks for `.global` symbol export
- **Tree-Shaking Dead Code Elimination** — the compiler natively builds dependency graphs of function calls and slices out unused standard library functions, reducing final binary sizes by up to 70%.
- **Self-Hosted Assembler & Linker** — integrated in-process x86_64 and ARM64 assembly/linking paths; Unix targets currently use GCC for final linking.
- **Variable-to-Register Promotion** — greedily maps local variables to CPU registers (`esi`/`edi`), massively boosting runtime performance.
- **Native Standard Library Injection** — standard library functions (from `os_windows`, `os_unix`, and built-in runtime helpers) are automatically injected and natively compiled into all executables, removing the need for manual imports of core modules.
- **Automatic PRNG Initialization** — the built-in xorshift64 PRNG automatically seeds itself at runtime via `sys_get_tick_count()`. `chacha20_init(seed1, seed2)` seeds the same state (name retained for compatibility).
- **HashMap/Dictionary** — `{"key": value}` literals with native codegen for `get()`, `set()`, `has()`, `remove()`, `keys()`, `values()`, `items()`, `len()`
- **Switch/match** — `switch expr { case val { body } else { body } }` desugars to if-elif chain at parse time
- **List comprehensions** — `[expr for x in list if cond]` desugars to Block + ForIn + append at parse time
- **Exceptions (try/catch/throw)** — full implementation with `setjmp`/`longjmp` native runtime, 10 tests
- **REPL** — `nova repl` interactive Read-Eval-Print Loop with multi-line input and persistent state
- **Cross-compilation** — `target_os`-aware codegen with platform-specific GCC commands and output extension
- **Frame pointer optimization** — x86_64 and ARM64 use `rsp`/`sp`-relative offsets, saving 1-2 instructions per function call
- **VM self-hosting** — `stdlib/vm.nv` implements bytecode VM in Nova with 20+ opcodes, stack-based execution
- Self-hosted lexer, parser, codegen, type checker, assembler, linker, VM

### Compatibility note

`call(name, args)` is supported by the VM but intentionally rejected by native
builds because native dynamic dispatch is not implemented. Use statically named
calls when a program must work in both modes.

## License

CC BY-NC 4.0 — personal/educational use allowed; commercial use prohibited.
