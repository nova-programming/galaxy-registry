import ast, os, re, sys

def _to_nova(node):
    if isinstance(node, ast.Module):
        return "\n".join(_to_nova(stmt) for stmt in node.body if isinstance(stmt, (ast.FunctionDef, ast.ClassDef, ast.If)))
    if isinstance(node, ast.ClassDef):
        return "\n".join(_to_nova(stmt) for stmt in node.body)
    if isinstance(node, ast.FunctionDef):
        if node.name.startswith("__"): return ""
        body = "\n".join(_to_nova(stmt) for stmt in node.body)
        return f"def {node.name}(state: CodegenState, node: AstNode) {{\n{body}\n}}\n"
    if isinstance(node, ast.If):
        test = _to_nova(node.test)
        body = "\n".join(_to_nova(stmt) for stmt in node.body)
        orelse = ""
        if node.orelse:
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                orelse = f" elif {_to_nova(node.orelse[0].test)} {{\n" + "\n".join(_to_nova(s) for s in node.orelse[0].body) + "\n}"
            else:
                orelse = " else {\n" + "\n".join(_to_nova(stmt) for stmt in node.orelse) + "\n}"
        return f"if {test} {{\n{body}\n}}{orelse}"
    if isinstance(node, ast.Call):
        func = _to_nova(node.func)
        args = ", ".join(_to_nova(arg) for arg in node.args)
        if func == "self.assembly.append": return f"emit(state, {args})"
        if func == "self.data_section.append": return f"emit_data(state, {args})"
        if func.startswith("self."): return f"{func.replace('self.', '')}(state, {args})"
        if func == "isinstance": return f"{_to_nova(node.args[0])}.kind == \"{node.args[1].id}\""
        return f"{func}({args})"
    if isinstance(node, ast.Attribute):
        val = _to_nova(node.value)
        return "state." + node.attr if val == "self" else f"{val}.{node.attr}"
    if isinstance(node, ast.Name):
        if node.id == "self": return "state"
        if node.id == "True": return "1"
        if node.id == "False": return "0"
        return node.id
    if isinstance(node, ast.Constant):
        return f'"{node.value}"' if isinstance(node.value, str) else str(node.value)
    if isinstance(node, ast.JoinedStr):
        parts = []
        for val in node.values:
            if isinstance(val, ast.Constant): parts.append(f'"{val.value}"')
            elif isinstance(val, ast.FormattedValue):
                expr = _to_nova(val.value)
                parts.append(f"str({expr})" if "str(" not in expr else expr)
        return " + ".join(parts)
    if isinstance(node, ast.Return):
        return f"return {_to_nova(node.value)}" if node.value else "return"
    if isinstance(node, ast.Assign):
        targets = " = ".join(_to_nova(t) for t in node.targets)
        return f"{targets} = {_to_nova(node.value)}"
    if isinstance(node, ast.Expr):
        return _to_nova(node.value)
    return f"/* UNHANDLED: {type(node).__name__} */"

def _transpile_python(arch):
    path = f"compiler/backend/{arch}/codegen.py"
    with open(path) as f:
        tree = ast.parse(f.read())
    return _to_nova(tree)

def _port_arm():
    path_expr = "stdlib/backend/arm64/codegen_expr.nv"
    path_stmt = "stdlib/backend/arm64/codegen_stmt.nv"
    for path in (path_expr, path_stmt):
        with open(path) as f:
            content = f.read()
        content = re.sub(r'push (%[abcd])', r'str \1, [sp, #-16]!', content)
        content = re.sub(r'pop (%[abcd])', r'ldr \1, [sp], #16', content)
        content = content.replace("push 0", "mov x0, 0\n        emit(state, \"    str x0, [sp, #-16]!\")")
        content = content.replace("push 1", "mov x0, 1\n        emit(state, \"    str x0, [sp, #-16]!\")")
        content = re.sub(r'add (%[abcd]), (%[abcd])', r'add \1, \1, \2', content)
        content = re.sub(r'sub (%[abcd]), (%[abcd])', r'sub \1, \1, \2', content)
        content = re.sub(r'imul (%[abcd]), (%[abcd])', r'mul \1, \1, \2', content)
        content = content.replace('emit(state, "    cqo")', '')
        content = re.sub(r'idiv (%[abcd])', r'sdiv %a, %a, \1', content)
        content = content.replace('emit(state, "    push %d")', 'emit(state, "    str %a, [sp, #-16]!")')
        content = re.sub(r'xor (%[abcd]), \1', r'mov \1, 0', content)
        content = re.sub(r'sete (%[abcd])', r'cset \1, eq', content)
        content = re.sub(r'setne (%[abcd])', r'cset \1, ne', content)
        content = re.sub(r'setg (%[abcd])', r'cset \1, gt', content)
        content = re.sub(r'setl (%[abcd])', r'cset \1, lt', content)
        content = re.sub(r'setge (%[abcd])', r'cset \1, ge', content)
        content = re.sub(r'setle (%[abcd])', r'cset \1, le', content)
        content = re.sub(r'movzx (%[abcd]), [a-z]+', r'', content)
        content = re.sub(r'jmp (L_[A-Za-z0-9_]+)', r'b \1', content)
        content = re.sub(r'je (L_[A-Za-z0-9_]+)', r'b.eq \1', content)
        content = re.sub(r'jne (L_[A-Za-z0-9_]+)', r'b.ne \1', content)
        content = re.sub(r'call (.*)', r'bl \1', content)
        content = content.replace('emit(state, "    mov [%b - " + str(0 - offset) + "], %a")', 'emit(state, "    str %a, [%b, #" + str(offset) + "]")')
        content = content.replace('emit(state, "    mov [%b - " + str(offset) + "], %a")', 'emit(state, "    str %a, [%b, #-" + str(offset) + "]")')
        content = content.replace('emit(state, "    mov %a, [%b - " + str(0 - offset) + "]")', 'emit(state, "    ldr %a, [%b, #" + str(offset) + "]")')
        content = content.replace('emit(state, "    mov %a, [%b - " + str(offset) + "]")', 'emit(state, "    ldr %a, [%b, #-" + str(offset) + "]")')
        content = content.replace('emit(state, "    lea %a, [rip + " + ', 'emit(state, "    adrp %a, " + node.val_str + "@PAGE")\n            emit(state, "    add %a, %a, " + ')
        content = content.replace('@PAGE")\n            emit(state, "    add %a, %a, " + node.val_str + "]', '@PAGE")\n            emit(state, "    add %a, %a, " + node.val_str + "@PAGEOFF")')
        content = content.replace('emit(state, "    mov %a, [rip + " + ', 'emit(state, "    adrp %a, " + node.val_str + "@PAGE")\n            emit(state, "    ldr %a, [%a, " + ')
        content = content.replace('@PAGE")\n            emit(state, "    ldr %a, [%a, " + node.val_str + "]', '@PAGE")\n            emit(state, "    ldr %a, [%a, " + node.val_str + "@PAGEOFF]")')
        content = content.replace('emit(state, "    lea %a, [rip + " + label + "]")', 'emit(state, "    adrp %a, " + label + "@PAGE")\n        emit(state, "    add %a, %a, " + label + "@PAGEOFF")')
        content = re.sub(r'\beax\b', 'x0', content)
        content = re.sub(r'\bebx\b', 'x1', content)
        content = re.sub(r'\becx\b', 'x2', content)
        content = re.sub(r'\bedx\b', 'x3', content)
        with open(path, "w") as f:
            f.write(content)
        print(f"Ported {path}")

def _fix_calls():
    pairs = [
        ("stdlib/backend/x86_64/codegen_expr.nv", "call"),
        ("stdlib/backend/x86_64/codegen_stmt.nv", "call"),
        ("stdlib/backend/arm64/codegen_expr.nv", "bl"),
        ("stdlib/backend/arm64/codegen_stmt.nv", "bl"),
    ]
    regex = re.compile(r'([ \t]*)emit\(state, "(?:    )?' + r'(call|bl)' + r' (.*?)"\)\n([ \t]*clean_n\(state, (.*?)\))?')
    for path, call_insn in pairs:
        if not os.path.exists(path): continue
        with open(path) as f:
            content = f.read()
        def _repl(m):
            indent = m.group(1)
            func_name = m.group(2)
            has_clean = m.group(3)
            arg_count = m.group(4) if has_clean else "0"
            if '" +' not in func_name and '+ "' not in func_name:
                func_name = f'"{func_name}"'
            return f'{indent}emit_call(state, {func_name}, {arg_count})'
        new_content = regex.sub(_repl, content)
        with open(path, "w") as f:
            f.write(new_content)
        print(f"Fixed calls in {path}")

def _cmd_x86_64(): print(_transpile_python("x86_64"))
def _cmd_arm64(): print(_transpile_python("arm64")[:1000])
def _cmd_port_arm(): _port_arm()
def _cmd_fix_calls(): _fix_calls()

if __name__ == "__main__":
    cmds = {
        "x86_64": _cmd_x86_64,
        "arm64": _cmd_arm64,
        "port-arm": _cmd_port_arm,
        "fix-calls": _cmd_fix_calls,
    }
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(f"Usage: python transpile.py <{'|'.join(cmds)}>")
        sys.exit(1)
    cmds[sys.argv[1]]()
