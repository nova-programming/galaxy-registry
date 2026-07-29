from nova_ast.nodes import *
from compiler.types import *

# Built-in FFI function signatures: (return_type, [param_types])
BUILTIN_SIGS = {
    "abs":           (IntType, [IntType]),
    "min":           (IntType, [IntType, IntType]),
    "max":           (IntType, [IntType, IntType]),
    "file_exists":   (IntType, [StringType]),
    "file_size":     (IntType, [StringType]),
    "file_type":     (StringType, [StringType]),
    "now":           (StringType, []),
    "sys_open":      (IntType, [StringType, StringType]),
    "sys_read":      (StringType, [IntType]),
    "sys_write":     (AnyType(), [IntType, AnyType()]),
    "sys_close":     (AnyType(), [IntType]),
    "sys_alloc":     (AnyType(), [IntType]),
    "sys_free":      (AnyType(), [AnyType()]),
    "sys_exit":      (AnyType(), [IntType]),
    "sys_platform":  (StringType, []),
    "sys_flush":     (AnyType(), [IntType]),
    "sys_system":    (IntType, [StringType]),
    "sys_get_args":  (ListType(AnyType()), []),
    "sys_get_tick_count": (IntType, []),
    "type":          (StringType, [AnyType()]),
    "call":          (AnyType(), [StringType, ListType(AnyType())]),
    "print":         (AnyType(), [AnyType()]),
    "len":           (IntType, [AnyType()]),
    "char_code":     (IntType, [StringType, IntType]),
    "str_sub":       (StringType, [StringType, IntType, IntType]),
}

class StaticTypeError(Exception):
    def __init__(self, message, line=None, suggestion="", col=None):
        self.line = line
        self.col = col
        prefix = f"[line {line}]" if line else ""
        if suggestion:
            super().__init__(f"{prefix} {message}\n  -> {suggestion}")
        else:
            super().__init__(f"{prefix} {message}")

class TypeInferer:
    def __init__(self):
        self.env_stack = [{}]
        self.structs = {}  # name -> StructType
        self.functions = {} # name -> FuncType
        self.current_function_return_type = None
        self.in_raw = False
        self.const_vars = set()

    def push_env(self):
        self.env_stack.append({})

    def pop_env(self):
        self.env_stack.pop()

    def set_var_type(self, name, type_obj):
        self.env_stack[-1][name] = type_obj

    def get_var_type(self, name):
        for env in reversed(self.env_stack):
            if name in env:
                return env[name]
        return AnyType()

    def unify(self, t1, t2, node=None):
        if isinstance(t1, DynType) or isinstance(t2, DynType):
            return DynType()
        if isinstance(t1, AnyType): return t2
        if isinstance(t2, AnyType): return t1
        
        if t1 == t2:
            return t1
            
        # Float and Int coerce
        if (isinstance(t1, ScalarType) and isinstance(t2, ScalarType)):
            if (t1.name == "float" and t2.name == "int") or (t1.name == "int" and t2.name == "float"):
                return FloatType
                
        # Null pointer support (0 as struct/list/func pointer)
        if isinstance(t1, ScalarType) and t1.name == "int" and (isinstance(t2, StructType) or isinstance(t2, ListType) or isinstance(t2, FuncType)):
            return t2
        if isinstance(t2, ScalarType) and t2.name == "int" and (isinstance(t1, StructType) or isinstance(t1, ListType) or isinstance(t1, FuncType)):
            return t1
                
        line = node.line if node and hasattr(node, 'line') else '?'
        raise StaticTypeError(
            f"Type mismatch: cannot use {t1} where {t2} is expected",
            line,
            f"try converting the value with int() or str(), or use a variable of type {t2}"
        )

    def visit(self, node):
        if node is None:
            return AnyType()

        method_name = f"visit_{type(node).__name__}"
        if hasattr(self, method_name):
            t = getattr(self, method_name)(node)
        else:
            t = AnyType()

        node.inferred_type = t
        return t

    def infer(self, ast):
        # Pass 1: Register structs and functions
        for stmt in ast:
            if isinstance(stmt, Data):
                struct_type = StructType(stmt.name)
                # We can't fully resolve field types yet until all structs are registered
                self.structs[stmt.name] = struct_type
            elif isinstance(stmt, Function):
                params = []
                for p_name, p_type_str in stmt.params:
                    params.append(resolve_type_annotation(p_type_str))
                ret_type = resolve_type_annotation(stmt.return_type)
                func_type = FuncType(params, ret_type)
                self.functions[stmt.name] = func_type

        # Pass 1.5: Resolve struct fields
        for stmt in ast:
            if isinstance(stmt, Data):
                struct_type = self.structs[stmt.name]
                for f_name, f_type_str in stmt.fields:
                    struct_type.fields[f_name] = resolve_type_annotation(f_type_str)

        # Pass 2: Infer everything
        for stmt in ast:
            self.visit(stmt)

    # --- Node Visitors ---

    def visit_Number(self, node):
        return IntType if isinstance(node.value, int) else FloatType

    def visit_String(self, node):
        return StringType

    def visit_Boolean(self, node):
        return BoolType

    def visit_Variable(self, node):
        t = self.get_var_type(node.name)
        return t

    def visit_BinOp(self, node):
        left_t = self.visit(node.left)
        right_t = self.visit(node.right)
        return self.unify(left_t, right_t, node)

    def visit_UnaryOp(self, node):
        return self.visit(node.value)

    def visit_Compare(self, node):
        self.visit(node.left)
        self.visit(node.right)
        return BoolType

    def visit_Assignment(self, node):
        t = self.visit_Assignment_real(node)
        return t

    def visit_Assignment_real(self, node):
        val_t = self.visit(node.value)

        if node.name in self.const_vars and not node.is_const:
            raise StaticTypeError(f"Cannot reassign const variable '{node.name}'", node.line,
                "remove the 'const' keyword from the declaration or use a different variable name")
        if node.is_const:
            self.const_vars.add(node.name)

        # Check existing type
        existing_t = None
        for env in reversed(self.env_stack):
            if node.name in env:
                existing_t = env[node.name]
                break
                
        if existing_t:
            if not isinstance(existing_t, DynType):
                self.unify(existing_t, val_t, node)
            t = existing_t
        else:
            declared_t = resolve_type_annotation(node.type_name) if node.type_name else val_t
            if node.type_name:
                self.unify(declared_t, val_t, node)
            self.set_var_type(node.name, declared_t)
            t = declared_t
            
        return t

    def visit_Function(self, node):
        if node.name == "main":
            raise StaticTypeError(
                "Cannot declare a function named 'main'",
                node.line,
                "the function name 'main' is reserved for the executable's entry point. Please rename it (e.g. to 'run' or 'start')"
            )
        self.push_env()
        prev_ret = self.current_function_return_type
        
        func_type = self.functions[node.name]
        self.current_function_return_type = func_type.ret
        
        for (p_name, _), p_type in zip(node.params, func_type.params):
            self.set_var_type(p_name, p_type)

        for stmt in node.body:
            self.visit(stmt)

        self.current_function_return_type = prev_ret
        self.pop_env()
        return func_type

    def visit_Return(self, node):
        t = self.visit(node.value)
        if self.current_function_return_type:
            self.unify(self.current_function_return_type, t, node)
        return t

    def visit_Call(self, node):
        # Function types
        if node.name in self.functions:
            func_type = self.functions[node.name]
            if len(node.args) != len(func_type.params):
                raise StaticTypeError(f"Function {node.name} expects {len(func_type.params)} args, got {len(node.args)}", node.line,
                    f"add or remove arguments to match the function signature — expected {len(func_type.params)}, got {len(node.args)}")
            
            for arg, param_type in zip(node.args, func_type.params):
                arg_t = self.visit(arg)
                self.unify(param_type, arg_t, arg)
                
            return func_type.ret
            
        # Struct instantiation (faked as Call currently)
        if node.name in self.structs:
            for arg in node.args:
                self.visit(arg)
            return self.structs[node.name]

        # Built-in FFI functions registered with known signatures
        if node.name in BUILTIN_SIGS:
            ret_type, param_types = BUILTIN_SIGS[node.name]
            if len(node.args) != len(param_types):
                raise StaticTypeError(f"Built-in {node.name} expects {len(param_types)} args, got {len(node.args)}", node.line)
            for arg, param_type in zip(node.args, param_types):
                arg_t = self.visit(arg)
                if param_type is not AnyType():
                    self.unify(param_type, arg_t, arg)
            return ret_type

        # FFI or unknown builtins
        for arg in node.args:
            self.visit(arg)
        return AnyType()

    def visit_IfElse(self, node):
        self.visit(node.condition)
        
        self.push_env()
        for stmt in node.if_body:
            self.visit(stmt)
        self.pop_env()

        self.push_env()
        for stmt in node.else_body:
            self.visit(stmt)
        self.pop_env()
        return AnyType()

    def visit_While(self, node):
        self.visit(node.condition)
        self.push_env()
        for stmt in node.body:
            self.visit(stmt)
        self.pop_env()
        return AnyType()

    def visit_ForLoop(self, node):
        self.push_env()
        start_t = self.visit(node.start)
        self.set_var_type(node.var_name, start_t)
        self.visit(node.end)
        self.visit(node.step)

        for stmt in node.body:
            self.visit(stmt)
        self.pop_env()
        return AnyType()

    def visit_ForIn(self, node):
        self.push_env()
        coll_t = self.visit(node.collection)
        var_t = AnyType()
        if isinstance(coll_t, ListType):
            var_t = coll_t.element_type
        self.set_var_type(node.var_name, var_t)
        
        for stmt in node.body:
            self.visit(stmt)
        self.pop_env()
        return AnyType()

    def visit_ClassDef(self, node):
        for method in node.methods:
            self.visit(method)
        return AnyType()

    def visit_MethodCall(self, node):
        inst_t = self.visit(node.instance)
        for arg in node.args:
            self.visit(arg)
        # FileType method validation
        if isinstance(inst_t, ScalarType) and inst_t.name == "file":
            if node.method_name == "write":
                if len(node.args) != 1:
                    raise StaticTypeError("file.write() expects exactly 1 argument", node.line,
                        "usage: file_var.write(\"content\")")
                return AnyType()
            elif node.method_name == "awrite":
                if len(node.args) != 1:
                    raise StaticTypeError("file.awrite() expects exactly 1 argument", node.line,
                        "usage: file_var.awrite(\"content\")")
                return AnyType()
            elif node.method_name == "close":
                if len(node.args) != 0:
                    raise StaticTypeError("file.close() takes no arguments", node.line,
                        "usage: file_var.close()")
                return AnyType()
            elif node.method_name == "read":
                if len(node.args) != 0:
                    raise StaticTypeError("file.read() takes no arguments", node.line,
                        "usage: file_var.read()")
                return StringType
            else:
                raise StaticTypeError(f"File object has no method '{node.method_name}'", node.line,
                    "available methods: .write(content), .awrite(content), .close(), .read()")
        return AnyType()

    def visit_PrintD(self, node):
        self.visit(node.value)
        return AnyType()

    def visit_Print(self, node):
        self.visit(node.value)
        return AnyType()

    def visit_Import(self, node):
        return AnyType()

    def visit_RawBlock(self, node):
        prev_raw = self.in_raw
        self.in_raw = True
        for stmt in node.body:
            self.visit(stmt)
        self.in_raw = prev_raw
        return AnyType()

    def visit_Export(self, node):
        return AnyType()

    def visit_Block(self, node):
        for stmt in node.stmts[:-1]:
            self.visit(stmt)
        return self.visit(node.stmts[-1])

    def visit_Try(self, node):
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.catch_body:
            self.visit(stmt)
        return AnyType()

    def visit_Throw(self, node):
        self.visit(node.value)
        return AnyType()

    def visit_Data(self, node):
        return self.structs[node.name]

    def visit_DataFieldAssign(self, node):
        inst_t = self.visit(node.instance)
        val_t = self.visit(node.value)
        if isinstance(inst_t, StructType) and node.field_name in inst_t.fields:
            self.unify(inst_t.fields[node.field_name], val_t, node)
        return val_t

    def visit_DataFieldAccess(self, node):
        inst_t = self.visit(node.instance)
        if isinstance(inst_t, StructType) and node.field_name in inst_t.fields:
            return inst_t.fields[node.field_name]
        return AnyType()

    def visit_LoadLib(self, node):
        return AnyType()

    def visit_Alloc(self, node):
        self.visit(node.size)
        return AnyType()

    def visit_Free(self, node):
        self.visit(node.ptr)
        return AnyType()

    def visit_PointerProperty(self, node):
        self.visit(node.ptr)
        return AnyType()

    def visit_PointerAssign(self, node):
        self.visit(node.ptr)
        self.visit(node.value)
        return AnyType()

    def visit_ArrayIndex(self, node):
        base_t = self.visit(node.base)
        self.visit(node.index)
        if isinstance(base_t, ListType):
            return base_t.element_type
        if isinstance(base_t, ScalarType) and base_t.name == "string":
            return StringType
        return AnyType()

    def visit_Slice(self, node):
        base_t = self.visit(node.base)
        if node.start: self.visit(node.start)
        if node.end: self.visit(node.end)
        if isinstance(base_t, ListType):
            return base_t
        if isinstance(base_t, ScalarType) and base_t.name == "string":
            return StringType
        return AnyType()

    def visit_ArrayIndexAssign(self, node):
        base_t = self.visit(node.base)
        self.visit(node.index)
        val_t = self.visit(node.value)
        if isinstance(base_t, ListType):
            self.unify(base_t.element_type, val_t, node)
        return val_t

    def visit_SizeOf(self, node):
        self.visit(node.target)
        return IntType

    def visit_Len(self, node):
        self.visit(node.target)
        return IntType

    def visit_StrConvert(self, node):
        self.visit(node.target)
        return StringType

    def visit_OpenFile(self, node):
        self.visit(node.path)
        self.visit(node.mode)
        return IntType

    def visit_ReadFile(self, node):
        self.visit(node.fd)
        return StringType

    def visit_WriteFile(self, node):
        self.visit(node.fd)
        self.visit(node.content)
        return AnyType()

    def visit_CloseFile(self, node):
        self.visit(node.fd)
        return AnyType()

    def visit_Openf(self, node):
        self.visit(node.path)
        if hasattr(node, 'mode') and node.mode:
            self.visit(node.mode)
        return FileType

    def visit_Self(self, node):
        return AnyType()

    def visit_Break(self, node):
        return AnyType()

    def visit_Continue(self, node):
        return AnyType()

    def visit_ListLiteral(self, node):
        elem_t = AnyType()
        for element in node.elements:
            t = self.visit(element)
            if isinstance(elem_t, AnyType):
                elem_t = t
            else:
                try:
                    elem_t = self.unify(elem_t, t, element)
                except StaticTypeError:
                    elem_t = AnyType()
        return ListType(elem_t)

    def visit_DictLiteral(self, node):
        for k, v in zip(node.keys, node.values):
            self.visit(k)
            self.visit(v)
        return DictType()

    def visit_DataInstance(self, node):
        # Unused currently, struct instantiation goes through Call
        return AnyType()
