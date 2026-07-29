importScripts("https://cdn.jsdelivr.net/pyodide/v0.25.0/full/pyodide.js");

let pyodide = null;
let initialized = false;

async function fetchPythonFile(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error("Failed to fetch " + path);
    return await res.text();
}

async function loadNovaFiles() {
    // We need to create directories and write files in Pyodide FS
    const files = [
        "lexer/__init__.py", "lexer/lexer.py", "lexer/tokens.py",
        "parser/__init__.py", "parser/parser.py",
        "nova_ast/__init__.py", "nova_ast/nodes.py", "nova_ast/visitor.py",
        "modules/__init__.py", "modules/resolver.py",
        "vm/__init__.py", "vm/vm.py", "vm/opcodes.py", "vm/compiler.py",
        "compiler/__init__.py", "compiler/types.py", "compiler/type_checker.py"
    ];

    for (const f of ["lexer", "parser", "nova_ast", "modules", "vm", "compiler"]) {
        try { pyodide.FS.mkdir(f); } catch(e) {}
    }

    for (const file of files) {
        const content = await fetchPythonFile("nova_compiler/" + file);
        pyodide.FS.writeFile(file, content);
    }
}

async function init() {
    postMessage({ type: "status", msg: "Loading Pyodide..." });
    pyodide = await loadPyodide({
        indexURL: "https://cdn.jsdelivr.net/pyodide/v0.25.0/full/"
    });
    
    postMessage({ type: "status", msg: "Loading Nova Compiler..." });
    await loadNovaFiles();
    
    // Create the runner script in Pyodide
    pyodide.runPython(`
import sys
import io
import traceback
from lexer.lexer import Lexer
from parser.parser import Parser
from compiler.type_checker import TypeChecker
from vm.compiler import VMCompiler
from vm.vm import VM

def run_nova(source_code):
    # Redirect stdout to capture print() output
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    
    output = ""
    error = ""
    try:
        lexer = Lexer(source_code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        checker = TypeChecker()
        checker.check(ast)
        
        vm_compiler = VMCompiler()
        vm_compiler.compile(ast)
        
        vm = VM(vm_compiler.instructions, vm_compiler.constants)
        vm.run()
        
        output = sys.stdout.getvalue()
    except Exception as e:
        error = str(e)
        # error = traceback.format_exc()
    finally:
        sys.stdout = old_stdout
        
    return {"output": output, "error": error}

def check_syntax(source_code):
    try:
        lexer = Lexer(source_code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        parser.parse()
        return {"error": ""}
    except Exception as e:
        return {"error": str(e)}
    `);
    
    initialized = true;
    postMessage({ type: "status", msg: "Ready", ready: true });
}

self.onmessage = async (e) => {
    if (!initialized) {
        postMessage({ type: "error", msg: "Compiler not ready yet." });
        return;
    }
    
    const { id, action, code } = e.data;
    
    if (action === "run") {
        try {
            const run_func = pyodide.globals.get("run_nova");
            const resultProxy = run_func(code);
            const result = resultProxy.toJs();
            resultProxy.destroy();
            postMessage({ type: "result", id, ...result });
        } catch (err) {
            postMessage({ type: "result", id, error: err.toString() });
        }
    } else if (action === "check") {
        try {
            const check_func = pyodide.globals.get("check_syntax");
            const resultProxy = check_func(code);
            const result = resultProxy.toJs();
            resultProxy.destroy();
            postMessage({ type: "check_result", id, ...result });
        } catch (err) {
            postMessage({ type: "check_result", id, error: err.toString() });
        }
    }
};

init().catch(err => {
    postMessage({ type: "error", msg: "Initialization failed: " + err });
});

