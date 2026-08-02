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
        "lexer/__init__.py", "lexer/tokenizer.py", "lexer/tokens.py",
        "parser/__init__.py", "parser/parser.py",
        "nova_ast/__init__.py", "nova_ast/nodes.py",
        "modules/__init__.py", "modules/resolver.py",
        "vm/__init__.py", "vm/machine.py", "vm/opcodes.py", "vm/compiler.py",
        "compiler/types.py", "compiler/type_checker.py"
    ];

    for (const f of ["lexer", "parser", "nova_ast", "modules", "vm", "compiler"]) {
        try { pyodide.FS.mkdir(f); } catch(e) {}
    }

    // Fetch directly from GitHub main branch
    const BASE_URL = "https://raw.githubusercontent.com/nova-programming/Nova/main/bootstrap/";
    for (const file of files) {
        const content = await fetchPythonFile(BASE_URL + file);
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
        is_bare_expr = False
        if len(ast) == 1:
            from nova_ast.nodes import Print, Assignment, Function, ClassDef, While, ForLoop, ForIn, IfElse, Return, Break, Continue, Data, EnumDef, Import, RawBlock, Try, Throw
            stmt = ast[0]
            if not isinstance(stmt, (Assignment, Function, ClassDef, Data, EnumDef, Import, RawBlock, Print, While, ForLoop, ForIn, IfElse, Return, Break, Continue, Try, Throw)):
                is_bare_expr = True
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
            resultProxy.destroy();
            postMessage({ type: "check_result", id, error });
        } catch (err) {
            postMessage({ type: "check_result", id, error: err.toString() });
        }
    }
};

init().catch(err => {
    postMessage({ type: "error", msg: "Initialization failed: " + err });
});

