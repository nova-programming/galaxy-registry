import sys
import os
import json
import hashlib
import urllib.request
import urllib.error
import zipfile
import io
import shutil
import re
import subprocess

# Make the bootstrap sub-packages (lexer, parser, ...) importable when launched
# as a console-script entry point (bootstrap.main:main) rather than as a script.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lexer.tokenizer import tokenize
from parser.parser import Parser
from vm.compiler import Compiler
from vm.machine import VirtualMachine
from compiler.type_checker import TypeInferer, StaticTypeError

NOVA_VERSION = "0.8.0"
REGISTRY_URL = "https://galaxy-registry.vercel.app"
NOVA_ZIP_URL = "https://github.com/nova-programming/Nova/archive/refs/heads/main.zip"
ZIP_PREFIX = "Nova-main"
NOVA_RELEASE_BASE = "https://github.com/nova-programming/Nova/releases/download"

ALLOWED_UPDATE_FILES = {"main.py", "_galaxy.py", "nova.nv", "runtime.c"}
ALLOWED_UPDATE_DIRS = {"bootstrap", "compiler", "parser", "lexer", "nova_ast", "vm", "stdlib", "modules", "tools", "galaxy"}

BUNDLED_GCC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gcc")


def _bundled_gcc_dirs(host):
    """Candidate dirs that may contain a bundled gcc/bin/gcc[.exe]."""
    dirs = [BUNDLED_GCC_DIR]
    if host == "windows":
        app = os.environ.get("LOCALAPPDATA", "")
        if app:
            dirs.append(os.path.join(app, "nova", "gcc"))
    else:
        home = os.path.expanduser("~")
        if home:
            dirs.append(os.path.join(home, ".nova", "gcc"))
    return dirs


def _gcc_machine(gcc_path):
    """Return the target machine string reported by gcc -dumpmachine, or None."""
    try:
        res = subprocess.run([gcc_path, "-dumpmachine"], capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None

def _host_os():
    """Detect the host operating system."""
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


CROSS_GCC_NAMES = {
    ("linux", "x86_64"):   "x86_64-linux-gnu-gcc",
    ("linux", "arm64"):    "aarch64-linux-gnu-gcc",
    ("windows", "x86_64"): "x86_64-w64-mingw32-gcc",
    ("windows", "arm64"):  "aarch64-w64-mingw32-gcc",
    ("macos", "x86_64"):   "x86_64-apple-darwin-gcc",
    ("macos", "arm64"):    "aarch64-apple-darwin-gcc",
}


def _find_gcc(target_os=None, target_arch="x86_64"):
    """Find GCC: bundled dir first, then system PATH. Supports cross-compilation."""
    host = _host_os()
    gcc_name = "gcc.exe" if host == "windows" else "gcc"
    # On macOS, prefer clang over gcc (gcc may be a stub that exits 1 silently)
    if host == "macos":
        clang = shutil.which("clang")
        if clang:
            return clang

    # Bundled compiler dirs (install location or repo checkout)
    for bdir in _bundled_gcc_dirs(host):
        bundled = os.path.join(bdir, "bin", gcc_name)
        if os.path.exists(bundled):
            return bundled

    # If cross-compiling, look for a cross-GCC toolchain on PATH
    if target_os and target_os != host:
        cross_key = (target_os, target_arch)
        cross_name = CROSS_GCC_NAMES.get(cross_key)
        if cross_name:
            cross = shutil.which(cross_name)
            if cross:
                return cross
        # Fallback: check bundled gcc dir for cross-GCC
        for bdir in _bundled_gcc_dirs(host):
            bundled_cross = os.path.join(bdir, "bin", cross_name if cross_name else gcc_name)
            if os.path.exists(bundled_cross):
                return bundled_cross

    # Native system GCC (must match host bitness to avoid 32-bit gas errors)
    system = shutil.which(gcc_name)
    if system:
        if target_os is None or target_os == host:
            machine = _gcc_machine(system)
            if machine and "64" not in machine.lower():
                return None
        return system

    # Last resort: try cross-GCC even without explicit target_os
    if target_os and target_os != host:
        cross_key = (target_os, target_arch)
        cross_name = CROSS_GCC_NAMES.get(cross_key)
        if cross_name:
            cross = shutil.which(cross_name)
            if cross:
                return cross

    return None


CACHE_FILE = ".nova_cache.json"


def _load_cache(project_dir):
    """Load the build cache dict from project directory."""
    path = os.path.join(project_dir, CACHE_FILE)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"version": NOVA_VERSION, "files": {}}


def _save_cache(project_dir, cache):
    """Save the build cache dict to project directory."""
    path = os.path.join(project_dir, CACHE_FILE)
    try:
        with open(path, "w") as f:
            json.dump(cache, f, indent=2)
    except OSError:
        pass


def _file_hash(file_path):
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            h.update(f.read())
        return h.hexdigest()
    except OSError:
        return None


def _build_fingerprint(file_path):
    """Hash of everything that affects the build output of file_path.

    Covers the source itself, sibling .nv modules it may import, the standard
    library, runtime.c and the bootstrap compiler, so editing any of them
    invalidates the cache (previously only the file itself was hashed, which
    could silently reuse a stale compiler after a stdlib change).
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    h = hashlib.sha256()
    paths = [os.path.abspath(file_path), os.path.join(root, "runtime.c")]
    src_dir = os.path.dirname(os.path.abspath(file_path))
    try:
        paths += [os.path.join(src_dir, n) for n in os.listdir(src_dir) if n.endswith(".nv")]
    except OSError:
        pass
    for sub, exts in (("stdlib", (".nv",)), ("bootstrap", (".py",))):
        for dirpath, dirnames, filenames in os.walk(os.path.join(root, sub)):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            paths += [os.path.join(dirpath, n) for n in filenames if n.endswith(exts)]
    for p in sorted(set(paths)):
        digest = _file_hash(p)
        if digest:
            h.update(os.path.relpath(p, root).encode("utf-8", "replace") if p.startswith(root) else p.encode("utf-8", "replace"))
            h.update(digest.encode())
    return h.hexdigest()


def _check_cache(project_dir, file_path):
    """Check if a file is unchanged since last build. Returns True if cached."""
    cache = _load_cache(project_dir)
    if cache.get("version") != NOVA_VERSION:
        return False
    fhash = _build_fingerprint(file_path)
    if fhash is None:
        return False
    return cache.get("files", {}).get(file_path) == fhash


def _update_cache(project_dir, file_path):
    """Update the cache with the current file hash."""
    cache = _load_cache(project_dir)
    cache["version"] = NOVA_VERSION
    fhash = _build_fingerprint(file_path)
    if fhash:
        cache["files"][file_path] = fhash
    _save_cache(project_dir, cache)


def format_error(source, lineno, offset, message, code=None, severity="error"):
    """Format a compiler error with source context.

    Shows the offending line with a ^ marker pointing at the column.
    lineno is 1-based, offset is 1-based (Python's SyntaxError convention).
    """
    label = f"{severity.capitalize()}{f' [{code}]' if code else ''}"
    if not source or not isinstance(lineno, int) or lineno < 1:
        return f"  {label}: {message}\n    |"
    lines = source.rstrip('\n').split('\n')
    if lineno > len(lines):
        return f"  {label} (line {lineno}): {message}\n    |"
    line = lines[lineno - 1]
    marker = ""
    if isinstance(offset, int) and offset > 0 and offset <= len(line) + 1:
        marker = " " * (offset - 1) + "^---"
    return (
        f"  {label} at line {lineno}:\n"
        f"    |\n"
        f"  {lineno:4d} | {line}\n"
        f"    | {marker}\n"
        f"    |\n"
        f"  {message}"
    )


def emit_diagnostic(message, code, severity="error", file_path=None,
                    line=None, column=None, json_output=False):
    """Emit stable diagnostics in human or opt-in JSON form."""
    if json_output:
        print(json.dumps({
            "code": code,
            "severity": severity,
            "message": message,
            "file": file_path,
            "line": line,
            "column": column,
        }, sort_keys=True))
    else:
        location = ""
        if file_path:
            location = file_path
            if line is not None:
                location += f":{line}"
                if column is not None:
                    location += f":{column}"
            location += ": "
        print(f"{location}{severity.capitalize()} [{code}]: {message}")


def _format_source(source):
    """Return a deterministic, non-semantic source normalization."""
    lines = [line.rstrip(" \t").replace("\t", "    ") for line in source.splitlines()]
    result = "\n".join(lines)
    return result + ("\n" if result or source.endswith(("\n", "\r")) else "")


def format_source(file_path, check_only=False, modernize=False):
    """Format whitespace only; writing requires the explicit --write flag.

    With modernize=True, old API spellings are also rewritten (see api_tools.modernize_source).
    """
    try:
        with open(file_path, "r", encoding="utf-8", newline="") as f:
            source = f.read()
    except OSError as e:
        emit_diagnostic(str(e), "IO001", file_path=file_path)
        return 1
    if modernize:
        import api_tools
        source_for_format = api_tools.modernize_source(source)
    else:
        source_for_format = source
    formatted = _format_source(source_for_format)
    if formatted == source:
        print(f"Formatted {os.path.basename(file_path)} successfully.")
        return 0
    if check_only:
        emit_diagnostic(
            "file is not canonically formatted; run 'nova fmt --write' to update it",
            "FMT001", "warning", file_path,
        )
        return 1
    with open(file_path, "w", encoding="utf-8", newline="") as f:
        f.write(formatted)
    print(f"Formatted {os.path.basename(file_path)}.")
    return 0


def _contains_dynamic_call(nodes, seen=None):
    """Return whether an AST contains the VM-only dynamic call() builtin."""
    from nova_ast.nodes import Call
    if seen is None:
        seen = set()
    if isinstance(nodes, (list, tuple)):
        return any(_contains_dynamic_call(item, seen) for item in nodes)
    if nodes is None or isinstance(nodes, (str, int, float, bool)):
        return False
    identity = id(nodes)
    if identity in seen:
        return False
    seen.add(identity)
    if isinstance(nodes, Call) and nodes.name == "call":
        return True
    if hasattr(nodes, "__dict__"):
        return any(_contains_dynamic_call(value, seen)
                   for value in vars(nodes).values())
    return False


def cmd_repl():
    """Start interactive Nova REPL."""
    import sys as _sys

    print(f"Nova v{NOVA_VERSION} REPL")
    print("Type 'exit' to quit, Ctrl+C to interrupt")
    print()

    persistent = {"env": {}, "functions": {}, "classes": {}}

    while True:
        try:
            line = input(">>> ")
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue

        if not line or line.strip() == "exit":
            break

        source = line.strip()

        # Multi-line input: accumulate lines until parse succeeds
        while True:
            try:
                tokens = tokenize(source)
                Parser(tokens).parse()
                break
            except SyntaxError as e:
                if "EOF" in str(e) or "Unexpected end" in str(e):
                    try:
                        extra = input("... ")
                    except (EOFError, KeyboardInterrupt):
                        print()
                        source += "\n"
                        break
                    if extra == "":
                        source += "\n"
                        break
                    source += "\n" + extra
                else:
                    break

        if not source.strip():
            continue

        try:
            tokens = tokenize(source)
            ast = Parser(tokens).parse()

            is_bare_expr = False
            if len(ast) == 1:
                from nova_ast.nodes import Print, Assignment, Function, ClassDef, While, ForLoop, ForIn, IfElse, Return, Break, Continue, Data, EnumDef, Import, RawBlock, Try, Throw
                stmt = ast[0]
                if not isinstance(stmt, (Assignment, Function, ClassDef, Data, EnumDef, Import, RawBlock, Print, While, ForLoop, ForIn, IfElse, Return, Break, Continue, Try, Throw)):
                    is_bare_expr = True
                    ast = [Print(stmt)]

            TypeInferer().infer(ast)

            from vm.compiler import Compiler
            compiler = Compiler()
            program = compiler.compile(ast)

            from vm.machine import VirtualMachine
            vm = VirtualMachine(program)
            vm.env.update(persistent["env"])
            vm.functions.update(persistent["functions"])
            vm.classes.update(persistent["classes"])
            vm.run()

            persistent["env"].update(vm.env)
            persistent["functions"].update(vm.functions)
            persistent["classes"].update(vm.classes)

        except SyntaxError as e:
            print(f"  SyntaxError: {e}")
        except Exception as e:
            print(f"  Error: {e}")


def run_source(file_path):
    """Run a Nova program in the VM (development mode — fast execution)."""
    file_path = os.path.abspath(file_path)
    base_dir = os.path.dirname(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        tokens = tokenize(source)
        ast = Parser(tokens).parse()
    except SyntaxError as e:
        print(format_error(source, getattr(e, 'lineno', None), getattr(e, 'offset', None), str(e)))
        sys.exit(1)

    try:
        TypeInferer().infer(ast)
    except StaticTypeError as e:
        print(format_error(source, getattr(e, 'line', None), getattr(e, 'col', None), str(e)))
        sys.exit(1)

    compiler = Compiler(base_dir=base_dir)
    program = compiler.compile(ast)

    vm = VirtualMachine(program)
    vm.run()


def check_source(file_path, target_arch="x86_64", target_os=None, json_output=False):
    """Parse, resolve imports, and type-check without producing or running code."""
    file_path = os.path.abspath(file_path)
    base_dir = os.path.dirname(file_path)
    if target_os is None:
        target_os = "macos" if sys.platform == "darwin" else ("windows" if sys.platform == "win32" else "linux")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        emit_diagnostic(str(e), "IO001", file_path=file_path, json_output=json_output)
        return 1

    try:
        tokens = tokenize(source)
        ast = Parser(tokens).parse()
        ast = expand_imports(ast, base_dir, target_arch=target_arch, target_os=target_os)
        TypeInferer().infer(ast)
    except SyntaxError as e:
        line = getattr(e, "lineno", None)
        column = getattr(e, "offset", None)
        if json_output:
            emit_diagnostic(str(e), "PARSE001", file_path=file_path,
                            line=line, column=column, json_output=True)
        else:
            print(format_error(source, line, column, str(e), code="PARSE001"))
        return 1
    except StaticTypeError as e:
        line = getattr(e, "line", None)
        column = getattr(e, "col", None)
        if json_output:
            emit_diagnostic(str(e), "TYPE001", file_path=file_path,
                            line=line, column=column, json_output=True)
        else:
            print(format_error(source, line, column, str(e), code="TYPE001"))
        return 1
    except Exception as e:
        emit_diagnostic(str(e), "CHECK001", file_path=file_path, json_output=json_output)
        return 1

    print(f"Checked {os.path.basename(file_path)} successfully.")
    return 0


def lint_source(file_path, strict=False, json_output=False):
    """Run advisory source checks without modifying the file."""
    file_path = os.path.abspath(file_path)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError as e:
        emit_diagnostic(str(e), "IO001", file_path=file_path, json_output=json_output)
        return 1

    import api_tools
    diagnostics = []
    defined_here = api_tools.defined_functions(chr(10).join(lines))
    function_pattern = re.compile(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    for line_number, line in enumerate(lines, 1):
        if line.rstrip(" \t") != line:
            diagnostics.append((line_number, "FMT002", "trailing whitespace"))
        if "\t" in line[:len(line) - len(line.lstrip())]:
            diagnostics.append((line_number, "STYLE001", "tabs used for indentation; use spaces"))
        match = function_pattern.match(line)
        if match and not re.fullmatch(r"[a-z][a-z0-9_]*|[a-z][a-zA-Z0-9]*", match.group(1)):
            diagnostics.append((line_number, "STYLE002",
                                f"function '{match.group(1)}' should use camelCase (or snake_case)"))
        for old_name, new_name in api_tools.old_spellings(line, defined_here):
            diagnostics.append((line_number, "STYLE003",
                                f"'{old_name}' is the old spelling; use '{new_name}' "
                                "(nova fmt --write --modernize rewrites it)"))
        if re.search(r"\b(?:alloc|free)\s*\(", line):
            diagnostics.append((line_number, "UNSAFE001",
                                "raw allocation requires explicit ownership review"))

    if diagnostics:
        for line_number, code, message in diagnostics:
            emit_diagnostic(message, code, "warning", file_path, line_number,
                            json_output=json_output)
        if strict:
            return 1
        if not json_output:
            print(f"Lint found {len(diagnostics)} advisory issue(s); build behavior was not changed.")
        return 0

    print(f"Linted {os.path.basename(file_path)} successfully.")
    return 0


def expand_imports(ast, base_dir, resolver=None, visited=None, target_arch="x86_64", target_os=None):
    from modules.resolver import ModuleResolver
    from nova_ast.nodes import Import
    import sys
    if target_os is None:
        target_os = "macos" if sys.platform == "darwin" else ("windows" if sys.platform == "win32" else "linux")
    if resolver is None:
        resolver = ModuleResolver(base_dir=base_dir, target_arch=target_arch, target_os=target_os)
    if visited is None:
        visited = set()

    expanded_ast = []
    for node in ast:
        if isinstance(node, Import):
            module_path = resolver._find_module(node.module, base_dir)
            visit_key = os.path.realpath(module_path) if module_path else node.module
            if visit_key not in visited:
                visited.add(visit_key)
                try:
                    imported_ast = resolver.resolve(node.module, base_dir)
                    imported_dir = os.path.dirname(module_path) if module_path else base_dir
                    # Recursively expand imports inside the imported file
                    expanded_ast.extend(expand_imports(imported_ast, imported_dir, resolver, visited, target_arch, target_os))
                except FileNotFoundError as e:
                    print(e)
                    sys.exit(1)
        else:
            expanded_ast.append(node)
    return expanded_ast


def compile_native(file_path, debug_mode=0, target_arch="x86_64", target_os=None, output=None):
    """Compile a Nova program to a native executable (build mode)."""
    file_path = os.path.abspath(file_path)
    base_dir = os.path.dirname(file_path)
    if target_os is None:
        target_os = "macos" if sys.platform == "darwin" else ("windows" if sys.platform == "win32" else "linux")

    if output:
        exe_file = output if os.path.isabs(output) else os.path.join(base_dir, output)
    else:
        output_ext = ".exe" if target_os == "windows" else ""
        exe_file = file_path.rsplit(".", 1)[0] + output_ext

    # Build cache: skip if source unchanged and output exists
    if not debug_mode and os.path.exists(exe_file) and _check_cache(base_dir, file_path):
        print(f"  [cached] {os.path.basename(file_path)} unchanged — {os.path.basename(exe_file)} is up to date")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        tokens = tokenize(source)
        ast = Parser(tokens).parse()
    except SyntaxError as e:
        print(format_error(source, getattr(e, 'lineno', None), getattr(e, 'offset', None), str(e)))
        sys.exit(1)
    
    # Collect module names before expansion
    from nova_ast.nodes import Import
    module_names = set()
    for node in ast:
        if isinstance(node, Import):
            module_names.add(node.module)

    ast = expand_imports(ast, base_dir, target_arch=target_arch, target_os=target_os)

    if _contains_dynamic_call(ast):
        print("Nova native build error: call(name, args) is VM-only; "
              "native dynamic dispatch is not implemented. "
              "Call a statically named function instead.")
        sys.exit(1)

    import infer
    infer.infer_return_types(ast)

    try:
        TypeInferer().infer(ast)
    except StaticTypeError as e:
        print(format_error(source, getattr(e, 'line', None), getattr(e, 'col', None), str(e)))
        sys.exit(1)

    source_path = os.path.basename(file_path)
    if target_arch == "arm64":
        from compiler.backend.arm64.codegen import Arm64Codegen
        codegen = Arm64Codegen(ast, module_names=module_names, debug_mode=debug_mode, target_os=target_os, source_path=source_path)
    else:
        from compiler.backend.x86_64.codegen import X86_64Codegen
        codegen = X86_64Codegen(ast, module_names=module_names, debug_mode=debug_mode, target_os=target_os, source_path=source_path)
        
    asm_code = codegen.generate()

    asm_file = file_path.rsplit(".", 1)[0] + ".s"

    with open(asm_file, "w", encoding="utf-8") as f:
        f.write(asm_code)

    print(f"Generated assembly: {asm_file}")
    
    nova_exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova.exe")
    nova_self = os.path.basename(exe_file) == "nova.exe"
    
    if os.path.exists(nova_exe) and not nova_self:
        try:
            asm_rel = os.path.relpath(asm_file)
            exe_rel = os.path.relpath(exe_file)
        except ValueError:
            asm_rel = asm_file
            exe_rel = exe_file
        cmd = [nova_exe, "assemble-link", asm_rel, exe_rel]
        print(f"Running: {' '.join(cmd)}")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            if os.path.exists(exe_file):
                if res.stdout:
                    print(res.stdout)
                print(f"Successfully compiled native executable: {exe_file}")
                _update_cache(base_dir, file_path)
                return
            print(f"Weird: nova.exe said OK but {exe_file} not found. Falling back to GCC.")
            if res.stdout:
                print(res.stdout)
        print(f"Nova assembler failed (code {res.returncode}), falling back to GCC")
        if res.stderr:
            print(res.stderr)
    
    gcc_path = _find_gcc(target_os=target_os, target_arch=target_arch)
    if not gcc_path:
        print()
        print("  [FAIL] GCC not found.")
        print("  Nova build requires a C compiler to link native executables.")
        print()
        print("  To install a C compiler:")
        if target_os == "windows":
            print("    Option 1: Download w64devkit from https://github.com/skeeto/w64devkit")
            print("    Option 2: Install MinGW-w64 from https://winlibs.com")
            print("    Option 3: Use 'nova dev <file.nv>' (runs via Python VM, no GCC needed)")
        elif target_os == "macos":
            print("    macOS: xcode-select --install")
        else:
            print("    Ubuntu/Debian: sudo apt install build-essential")
            print("    Fedora:        sudo dnf install gcc")
        print()
        print("  Or run in development mode (no compilation needed):")
        print("    nova dev <file.nv>")
        print()
        sys.exit(1)
    
    nova_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime_c = os.path.join(nova_root, "runtime.c")
    runtime_o = os.path.join(nova_root, "runtime.o")
    needs_runtime = target_arch in ("x86_64", "arm64")
    is_macos = target_os == "macos"
    is_windows = target_os == "windows"
    
    cmd = [gcc_path, "-O3", asm_file]

    if needs_runtime and os.path.exists(runtime_c):
        # Always recompile runtime.c to avoid stale object file issues
        if os.path.exists(runtime_o):
            os.remove(runtime_o)
        rt_cmd = [gcc_path, "-O3", "-c", runtime_c, "-o", runtime_o]
        if is_macos:
            rt_cmd += ["-D", "MACOS"]
            if target_arch == "arm64":
                rt_cmd += ["-arch", "arm64"]
        elif is_windows:
            rt_cmd += ["-mno-red-zone"]
        else:
            rt_cmd += ["-D", "LINUX_WRAP"]
        print(f"Compiling runtime.c: {' '.join(rt_cmd)}")
        rt_res = subprocess.run(rt_cmd)
        if rt_res.returncode != 0:
            print(f"  [WARN] runtime.c compilation failed (exit {rt_res.returncode})")
        if os.path.exists(runtime_o):
            cmd += [runtime_o]

    cmd += ["-o", exe_file]

    if is_windows:
        cmd += ["-mconsole", "-Wl,--stack,16777216", "-lkernel32", "-lgdi32", "-luser32"]
    elif is_macos:
        if target_arch == "arm64":
            cmd += ["-arch", "arm64"]
        cmd += ["-Wl,-no_compact_unwind"]
    else:
        cmd += ["-no-pie"]

    for lib in getattr(codegen, "linked_libs", []):
        clean_lib = lib.strip('"\'')
        if clean_lib:
            lib_flag = f"-l{clean_lib}"
            if lib_flag not in cmd:
                cmd.append(lib_flag)
    # Debug: show symbols in runtime.o on macOS
    if is_macos:
        try:
            nm_res = subprocess.run(["nm", "-g", runtime_o], capture_output=True, text=True, timeout=10)
            for line in nm_res.stdout.splitlines():
                print(f"  [NM] {line}")
            if nm_res.stderr:
                for line in nm_res.stderr.splitlines():
                    print(f"  [NM_ERR] {line}")
        except Exception as e:
            print(f"  [DEBUG] nm failed: {e}")
    
    print(f"Running command: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Compilation Failed:")
        print(res.stderr)
        sys.exit(1)
    print(f"Successfully compiled native executable: {exe_file}")
    _update_cache(base_dir, file_path)


def cmd_uninstall():
    """Remove Nova installation and all files it downloaded (GCC, launchers, galaxy_modules, etc)."""
    try:
        _do_uninstall()
    except KeyboardInterrupt:
        print("\n  Uninstall cancelled.")
        sys.exit(130)


def _do_uninstall():
    print(f"Nova v{NOVA_VERSION}")
    print()

    # Collect all directories to remove
    install_dirs = set()
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Detect install locations
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if os.name == "nt":
        candidates = [
            os.path.join(localappdata, "nova"),
            os.path.join(localappdata, "galaxy"),
            script_dir if "nova" in script_dir.lower() else None,
        ]
    else:
        candidates = [
            os.path.join(os.path.expanduser("~"), ".nova"),
            os.path.join(os.path.expanduser("~"), ".galaxy"),
        ]
    for d in candidates:
        if d and os.path.exists(d):
            install_dirs.add(d)

    # Check for galaxy_modules in specific install dirs only (avoid crawling entire home)
    for search_root in list(install_dirs):
        if search_root and os.path.exists(search_root):
            for root, dirs, files in os.walk(search_root):
                if "galaxy_modules" in dirs:
                    install_dirs.add(os.path.join(root, "galaxy_modules"))

    # Also check for galaxy_modules in typical project locations
    for loc in [script_dir, os.path.join(os.path.expanduser("~"), "projects")]:
        gm = os.path.join(loc, "galaxy_modules") if loc else None
        if gm and os.path.exists(gm):
            install_dirs.add(gm)

    if not install_dirs:
        print("  No Nova installation found. Nothing to uninstall.")
        return

    print("  This will remove the following:")
    for d in sorted(install_dirs):
        print(f"    {d}")
    print()
    answer = input("  Uninstall Nova? (y/N): ").strip().lower()
    if answer not in ("y", "yes"):
        print("  Uninstall cancelled.")
        return

    # Remove directories
    for d in sorted(install_dirs):
        try:
            shutil.rmtree(d)
            print(f"  Removed {d}")
        except Exception as e:
            print(f"  [WARN] Could not remove {d}: {e}")

    # Remove generated files in the script directory (compiler intermediates)
    for f in ["nova.s", "nova_main.s"]:
        gen = os.path.join(script_dir, f)
        if os.path.exists(gen):
            try:
                os.remove(gen)
                print(f"  Removed {gen}")
            except Exception:
                pass

    # Remove User PATH entries
    if os.name == "nt":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
            try:
                current, _ = winreg.QueryValueEx(key, "PATH")
                entries = current.split(";")
                filtered = [e for e in entries if "nova" not in e.lower() and "galaxy" not in e.lower()]
                new_path = ";".join(filtered)
                winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
                print("  Removed Nova/Galaxy from User PATH")
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
        except Exception:
            print("  [WARN] Could not update PATH automatically. Remove manually if needed.")
    else:
        for rc in [".bashrc", ".zshrc", ".profile", ".bash_profile"]:
            rc_path = os.path.join(os.path.expanduser("~"), rc)
            if os.path.exists(rc_path):
                with open(rc_path, "r") as f:
                    content = f.read()
                if "nova" in content.lower():
                    new_content = "\n".join(
                        line for line in content.split("\n")
                        if "nova" not in line.lower()
                    )
                    with open(rc_path, "w") as f:
                        f.write(new_content)
                    print(f"  Cleaned Nova references from ~/{rc}")

    print()
    print("  Nova has been uninstalled.")
    print("  Close and reopen your terminal for PATH changes to take effect.")


def run_native(file_path, target_arch="x86_64", target_os=None):
    """Build to native executable and run it."""
    if target_os is None:
        target_os = "macos" if sys.platform == "darwin" else ("windows" if sys.platform == "win32" else "linux")

    compile_native(file_path, target_arch=target_arch, target_os=target_os)

    output_ext = ".exe" if target_os == "windows" else ""
    exe_file = file_path.rsplit(".", 1)[0] + output_ext

    if not os.path.exists(exe_file):
        print(f"  Native build failed — falling back to VM execution.")
        run_source(file_path)
        return

    program_args = []
    try:
        idx = sys.argv.index(file_path)
        program_args = sys.argv[idx + 1:]
    except ValueError:
        pass
    cmd = [exe_file] + program_args
    print(f"  Executing: {' '.join(cmd)}")
    subprocess.run(cmd)


def print_usage():
    print("Nova Programming Language")
    print(f"Version: {NOVA_VERSION}")
    print("")
    print("Usage:")
    print("  nova --version            Show version")
    print("  nova dev <file.nv>       Run in VM (fast, for development)")
    print("  nova check <file.nv>     Parse and type-check without building")
    print("  nova lint <file.nv>      Show advisory style warnings (use --strict to fail)")
    print("  nova fmt <file.nv>       Check formatting; use --write to modify")
    print("                           (--modernize also rewrites old API names, e.g. fs_read -> fs.read)")
    print("  nova build <file.nv>     Compile to native executable")
    print("  nova run <file.nv>       Build native + execute (maximum speed)")
    print("  nova repl                Interactive REPL shell")
    print("  nova update              Update Nova compiler")
    print("  nova --uninstall         Remove Nova from your system")
    print("  nova galaxy <cmd>        Run Galaxy Package Manager")
    print("  galaxy <cmd>             Or use the standalone 'galaxy' command")
    print("")
    print("Examples:")
    print("  nova build hello.nv")
    print("  nova --uninstall")
    print("")
    print("Fallback (python):")
    print("  python main.py dev program.nv")
    print("  python main.py build program.nv")
    print("  python main.py repl")
    print("  python main.py --uninstall")


def _detect_install_dir():
    """Detect the Nova installation directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(script_dir, "main.py")):
        return script_dir
    known = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "nova"),
        os.path.join(os.path.expanduser("~"), ".nova"),
    ]
    for p in known:
        if p and os.path.exists(os.path.join(p, "main.py")):
            return p
    return script_dir


MAX_UPDATE_ARCHIVE_BYTES = 50 * 1024 * 1024


def extract_update_archive(zip_data, install_dir):
    """Extract an update zip into install_dir; returns the number of files written.

    Validates every member before writing anything: no absolute or ``..``
    paths, no symlinks, and the resolved destination must stay inside
    install_dir. Raises ValueError (without touching disk) on any violation.
    """
    if len(zip_data) > MAX_UPDATE_ARCHIVE_BYTES:
        raise ValueError("archive exceeds size limit")
    root = os.path.abspath(install_dir)
    planned = []
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        bad = zf.testzip()
        if bad is not None:
            raise ValueError(f"corrupted archive: {bad}")
        for info in zf.infolist():
            rel = info.filename.replace("\\", "/")
            if rel.startswith(ZIP_PREFIX + "/"):
                rel = rel[len(ZIP_PREFIX) + 1:]
            if not rel or rel.endswith("/"):
                continue
            parts = rel.split("/")
            if parts[0] not in ALLOWED_UPDATE_FILES and parts[0] not in ALLOWED_UPDATE_DIRS:
                continue
            if rel.startswith("/") or any(p in ("", ".", "..") or ":" in p for p in parts):
                raise ValueError(f"unsafe archive path: {info.filename}")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f"archive contains symlink: {info.filename}")
            dst = os.path.abspath(os.path.join(root, *parts))
            if not dst.startswith(root + os.sep):
                raise ValueError(f"unsafe archive path: {info.filename}")
            planned.append((info, dst))
        for info, dst in planned:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with zf.open(info) as src, open(dst, "wb") as df:
                shutil.copyfileobj(src, df)
    return len(planned)


def cmd_update():
    """Update the Nova compiler itself."""
    print(f"Nova v{NOVA_VERSION}")
    print()

    try:
        req = urllib.request.Request(
            f"{REGISTRY_URL}/versions/nova.json",
            headers={"User-Agent": "Nova/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        latest = data.get("version", "")
    except Exception as e:
        print(f"Could not check for updates ({e})")
        return

    if latest == NOVA_VERSION:
        print(f"Already up to date (v{NOVA_VERSION}).")
        return

    print(f"Latest version: v{latest}  (current: v{NOVA_VERSION})")
    answer = input(f"Update to v{latest}? (Y/n): ").strip().lower()
    if answer not in ("", "y", "yes"):
        print("Update cancelled.")
        return

    install_dir = _detect_install_dir()
    print(f"Install directory: {install_dir}")
    print("Downloading...")

    url = f"{NOVA_RELEASE_BASE}/nova-v{latest}/nova-v{latest}.zip"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Nova/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            zip_data = r.read()
    except Exception as e:
        print(f"Download failed ({e}). Falling back to full repo zip...")
        try:
            req = urllib.request.Request(NOVA_ZIP_URL, headers={"User-Agent": "Nova/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                zip_data = r.read()
        except Exception as e2:
            print(f"Download failed: {e2}")
            return

    print("Extracting...")
    try:
        count = extract_update_archive(zip_data, install_dir)
    except ValueError as e:
        print(f"Update aborted: {e}")
        return

    print(f"Updated {count} files.")
    print(f"Nova has been updated to v{latest}.")
    print("Restart your terminal or run 'nova --version' to confirm.")


def main():
    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1]

    if command in ("-v", "--version", "version"):
        print(f"Nova v{NOVA_VERSION}")
        return

    if command in ("--uninstall", "uninstall", "remove"):
        cmd_uninstall()
        return

    if command == "update":
        cmd_update()
        return

    if command == "galaxy":
        from tools.galaxy import main as galaxy_main
        old_argv = sys.argv
        sys.argv = ["galaxy"] + sys.argv[2:]
        galaxy_main()
        sys.argv = old_argv
        return

    if command in ("repl", "interactive", "shell"):
        cmd_repl()
        return

    if len(sys.argv) < 3:
        print_usage()
        return

    import platform
    debug_mode = 0
    bench_mode = 0
    target_arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x86_64"
    file_path = None
    output_file = None

    strict_lint = False
    json_output = False
    fmt_write = False
    fmt_modernize = False
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in ("-d", "--debug"):
            debug_mode = 1
        elif arg in ("-b", "--bench"):
            bench_mode = 1
        elif arg == "-o":
            if i + 1 < len(sys.argv):
                output_file = sys.argv[i+1]
                i += 1
            else:
                print("Error: -o requires an argument (output file)")
                return
        elif arg == "-arch":
            if i + 1 < len(sys.argv):
                target_arch = sys.argv[i+1]
                i += 1
            else:
                print("Error: -arch requires an argument (e.g. x86_64 or arm64)")
                return
        elif arg == "--os":
            if i + 1 < len(sys.argv):
                target_os = sys.argv[i+1]
                i += 1
            else:
                print("Error: --os requires an argument (e.g. windows, linux, macos)")
                return
        elif arg == "--strict":
            strict_lint = True
        elif arg == "--json":
            json_output = True
        elif arg == "--write":
            fmt_write = True
        elif arg == "--modernize":
            fmt_modernize = True
        else:
            file_path = arg
        i += 1

    if file_path is None:
        print_usage()
        return

    import time
    start_time = time.time()

    if command == "check":
        target_os_arg = locals().get("target_os")
        raise SystemExit(check_source(file_path, target_arch=target_arch,
                                      target_os=target_os_arg, json_output=json_output))
    elif command == "lint":
        raise SystemExit(lint_source(file_path, strict=strict_lint, json_output=json_output))
    elif command == "fmt":
        raise SystemExit(format_source(os.path.abspath(file_path), check_only=not fmt_write, modernize=fmt_modernize))
    elif command in ("dev",):
        run_source(file_path)
    elif command == "run":
        target_os_arg = locals().get("target_os")
        run_native(file_path, target_arch=target_arch, target_os=target_os_arg)
    elif command == "build":
        target_os_arg = locals().get("target_os")
        compile_native(file_path, debug_mode, target_arch=target_arch, target_os=target_os_arg, output=output_file)
    else:
        print(f"Unknown command: {command}")
        print_usage()
        
    if bench_mode:
        print(f"[Benchmark] Build completed in {int((time.time() - start_time) * 1000)} ms")


if __name__ == "__main__":
    main()