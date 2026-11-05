importScripts("https://cdn.jsdelivr.net/pyodide/v0.25.0/full/pyodide.js");

// Try to import bundled compiler files (instant startup, zero network fetch, immune to GitHub rate-limits or ISP blocks)
try {
    importScripts("nova_bundle.js");
} catch(e) {
    console.warn("Local nova_bundle.js not available, will fallback to network fetch", e);
}

// Compiler sources can also be fetched from GitHub if custom ?nova= is supplied.
const NOVA_REF = "main";
const customNovaParam = new URL(self.location.href).searchParams.get("nova");
const NOVA_RAW = customNovaParam ||
    "https://raw.githubusercontent.com/nova-programming/Nova/" + NOVA_REF + "/";

let pyodide = null;
let initialized = false;

async function fetchPythonFile(path) {
    const res = await fetch(path, { cache: "no-cache" });
    if (!res.ok) throw new Error("Failed to fetch " + path);
    return await res.text();
}

async function loadNovaFiles() {
    // Ensure all target directories exist in Pyodide virtual filesystem
    for (const f of ["lexer", "parser", "nova_ast", "modules", "vm", "compiler"]) {
        try { pyodide.FS.mkdir(f); } catch(e) {}
    }

    // Fast path: use bundled files (100% reliable, zero network dependency)
    if (self.NOVA_COMPILER_FILES && !customNovaParam) {
        for (const [file, content] of Object.entries(self.NOVA_COMPILER_FILES)) {
            pyodide.FS.writeFile(file, content);
        }
        return;
    }

    // Network fallback path (only if bundle is missing or custom ?nova= is specified)
    const files = [
        "lexer/__init__.py", "lexer/tokenizer.py", "lexer/tokens.py",
        "parser/__init__.py", "parser/parser.py",
        "nova_ast/__init__.py", "nova_ast/nodes.py",
        "modules/__init__.py", "modules/resolver.py",
        "vm/__init__.py", "vm/machine.py", "vm/opcodes.py", "vm/compiler.py",
        "compiler/types.py", "compiler/type_checker.py"
    ];
    const optionalFiles = ["names.py"];
    const optionalStdlib = ["text", "json"];

    const BASE_URL = NOVA_RAW + "bootstrap/";
    for (const file of files) {
        if (file === "vm/__init__.py") {
            // vm/__init__.py is 0 bytes in python, write empty string directly
            pyodide.FS.writeFile(file, "");
            continue;
        }
        try {
            const content = await fetchPythonFile(BASE_URL + file);
            pyodide.FS.writeFile(file, content);
        } catch(e) {
            // If empty file fails on some CDNs, create empty file
            if (file.endsWith("__init__.py")) {
                pyodide.FS.writeFile(file, "");
            } else {
                throw e;
            }
        }
    }
    for (const file of optionalFiles) {
        try { pyodide.FS.writeFile(file, await fetchPythonFile(BASE_URL + file)); } catch (e) {}
    }
    for (const mod of optionalStdlib) {
        try { pyodide.FS.writeFile(mod + ".nv", await fetchPythonFile(NOVA_RAW + "stdlib/" + mod + ".nv")); } catch (e) {}
    }
}

async function init() {
    postMessage({ type: "status", msg: "Initializing WebAssembly VM..." });
    pyodide = await loadPyodide({
        indexURL: "https://cdn.jsdelivr.net/pyodide/v0.25.0/full/"
    });
    
    postMessage({ type: "status", msg: "Loading Nova Compiler Core..." });
    await loadNovaFiles();
    
    // Create the runner & diagnostic syntax checker script in Pyodide
    pyodide.runPython(`
import sys
import io
import re
import traceback
from lexer.tokenizer import tokenize
from parser.parser import Parser
from compiler.type_checker import TypeInferer
from vm.compiler import Compiler
from vm.machine import VirtualMachine

def run_nova(source_code):
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    
    output = ""
    error = ""
    try:
        tokens = tokenize(source_code)
        parser = Parser(tokens)
        ast = parser.parse()
        
        # Handle bare expressions as prints for REPL-like behavior in playground
        if len(ast) == 1:
            from nova_ast.nodes import Print, Assignment, Function, ClassDef, While, ForLoop, ForIn, IfElse, Return, Break, Continue, Data, EnumDef, Import, RawBlock, Try, Throw
            stmt = ast[0]
            if not isinstance(stmt, (Assignment, Function, ClassDef, Data, EnumDef, Import, RawBlock, Print, While, ForLoop, ForIn, IfElse, Return, Break, Continue, Try, Throw)):
                ast = [Print(stmt)]
        
        checker = TypeInferer()
        checker.infer(ast)
        
        vm_compiler = Compiler()
        program = vm_compiler.compile(ast)
        
        vm = VirtualMachine(program)
        vm.run()
        
        output = sys.stdout.getvalue()
    except Exception as e:
        error = str(e)
    finally:
        sys.stdout = old_stdout
        
    return {"output": output, "error": error}

def check_syntax(source_code):
    try:
        tokens = tokenize(source_code)
        parser = Parser(tokens)
        parser.parse()
        return {"error": "", "line": 0}
    except Exception as e:
        msg = str(e)
        m = re.search(r'line\\s+(\\d+)', msg)
        line = int(m.group(1)) if m else 1
        return {"error": msg, "line": line}
    `);
    
    initialized = true;
    postMessage({ type: "status", msg: "Ready", ready: true });
}

self.onmessage = async (e) => {
    if (!initialized) {
        postMessage({ type: "error", msg: "Compiler not ready yet." });
        return;
    }
    
    const { id, action, code } = e.data || {};
    if (typeof code !== "string" || code.length > 200000) {
        postMessage({ type: "error", id, msg: "Source must be text under 200 KB." });
        return;
    }
    
    if (action === "run") {
        try {
            const run_func = pyodide.globals.get("run_nova");
            const resultProxy = run_func(code);
            const output = resultProxy.get("output");
            const error = resultProxy.get("error");
            resultProxy.destroy();
            postMessage({ type: "result", id, output, error });
        } catch (err) {
            postMessage({ type: "result", id, error: err.toString() });
        }
    } else if (action === "check") {
        try {
            const check_func = pyodide.globals.get("check_syntax");
            const resultProxy = check_func(code);
            const error = resultProxy.get("error");
            const line = resultProxy.get("line");
            resultProxy.destroy();
            postMessage({ type: "check_result", id, error, line });
        } catch (err) {
            postMessage({ type: "check_result", id, error: err.toString(), line: 1 });
        }
    }
};

init().catch(err => {
    postMessage({ type: "error", msg: "Initialization failed: " + err });
});
