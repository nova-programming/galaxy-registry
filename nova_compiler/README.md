# Frozen V1 Python Bootstrap Compiler

This directory contains the original Python-based Nova compiler.

**It is officially frozen and deprecated.**

We have fully transitioned to a self-hosted workflow. From now on, `nova.exe` (written in Nova via the `stdlib/` directory) is used to compile itself and all future Nova programs.

### Why does this directory exist?
It acts purely as an emergency fallback. If the `nova.exe` binary is accidentally deleted or broken, and there is no working backup, you can use `python main.py build stdlib/compiler.nv -o nova.exe` to bootstrap a V1 copy of the self-hosted compiler from source.

### Do not edit code here
If you are adding a new language feature, syntax, or backend capability to Nova, **do not** add it to these Python files. Only add it to the `stdlib/` compiler source!

### Recent cleanup
During the self-hosting bootstrap (June 2026), orphaned dead data (`str_const_sys_platform`) was removed from both bootstrap codegens (x86_64 and ARM64) — they never emitted the corresponding assembly function.
