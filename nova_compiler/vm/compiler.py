"""Custom compiler that translates AST to custom bytecode"""

import os
from .opcodes import OpCode
from nova_ast.nodes import *
from modules.resolver import ModuleResolver


class Compiler:
    def __init__(self, base_dir=None):
        self.code = []       # List of (opcode, arg)
        self.constants = []  # List of constant values
        self.strings = []    # List of string literals
        self.functions = {}  # name -> starting instruction index
        self.classes = {}    # name -> ClassDef node (metadata)
        self.loop_stack = [] # Stack of (start_idx, end_jump_indices)
        self.resolver = ModuleResolver(base_dir=base_dir)
        self.base_dir = base_dir or os.getcwd()

    def add_const(self, value):
        if value in self.constants:
            return self.constants.index(value)
        self.constants.append(value)
        return len(self.constants) - 1

    def add_string(self, value):
        if value in self.strings:
            return self.strings.index(value)
        self.strings.append(value)
        return len(self.strings) - 1

    def emit(self, opcode, arg=None):
        idx = len(self.code)
        self.code.append([opcode, arg])
        return idx

    def patch_jump(self, idx, target):
        self.code[idx][1] = target

    def compile_import(self, node):
        """Resolve and compile a .nv module import."""
        module_name = node.module
        try:
            imported_ast = self.resolver.resolve(module_name, self.base_dir)
        except FileNotFoundError as e:
            raise Exception(str(e))

        # First pass: collect functions, classes, and data from the imported module
        for stmt in imported_ast:
            if isinstance(stmt, ClassDef):
                self.classes[stmt.name] = stmt
            elif isinstance(stmt, Data):
                self.classes[stmt.name] = stmt
            elif isinstance(stmt, Function):
                self.functions[stmt.name] = {
                    "ip": -1,
                    "params": stmt.params
                }
            elif isinstance(stmt, RawBlock):
                for raw_stmt in stmt.body:
                    if isinstance(raw_stmt, Function):
                        self.functions[raw_stmt.name] = {
                            "ip": -1,
                            "params": raw_stmt.params
                        }

        # Second pass: compile function/method bodies from the imported module
        for stmt in imported_ast:
            if isinstance(stmt, ClassDef):
                for method in stmt.methods:
                    method_name = f"{stmt.name}.{method.name}"
                    self.functions[method_name] = {
                        "ip": len(self.code),
                        "params": method.params
                    }
                    self.compile_function_body(method)
            elif isinstance(stmt, Function):
                self.functions[stmt.name]["ip"] = len(self.code)
                self.compile_function_body(stmt)

        # Third pass: compile top-level statements (non-function/class) from the imported module
        for stmt in imported_ast:
            if not isinstance(stmt, (ClassDef, Function, Data, Import)):
                self.compile_stmt(stmt)

    def compile(self, statements):
        # We start by adding a jump to main. Later, we'll patch this.
        entry_jump = self.emit(OpCode.JUMP, 0)

        main_start = -1

        # Pre-pass: handle all imports first
        for stmt in statements:
            if isinstance(stmt, Import):
                self.compile_import(stmt)

        # First pass: collect classes and functions metadata
        for stmt in statements:
            if isinstance(stmt, ClassDef):
                self.classes[stmt.name] = stmt
            elif isinstance(stmt, Data):
                # Using classes dictionary to hold structs as well to simplify VM struct instantiation
                self.classes[stmt.name] = stmt
            elif isinstance(stmt, Function):
                # Ensure the function metadata includes the parameter names
                self.functions[stmt.name] = {
                    "ip": -1, # Set in second pass
                    "params": stmt.params
                }
            elif isinstance(stmt, RawBlock):
                for raw_stmt in stmt.body:
                    if isinstance(raw_stmt, Function):
                        self.functions[raw_stmt.name] = {
                            "ip": -1,
                            "params": raw_stmt.params
                        }

        # Second pass: compile functions/methods first, then main body statements

        for stmt in statements:
            if isinstance(stmt, ClassDef):
                # Compile methods
                for method in stmt.methods:
                    method_name = f"{stmt.name}.{method.name}"
                    self.functions[method_name] = {
                        "ip": len(self.code),
                        "params": method.params
                    }
                    self.compile_function_body(method)
            elif isinstance(stmt, Function):
                self.functions[stmt.name]["ip"] = len(self.code)
                self.compile_function_body(stmt)

        main_start = len(self.code)

        for stmt in statements:
            if not isinstance(stmt, (ClassDef, Function, Import)):
                self.compile_stmt(stmt)

        if main_start == -1:
            main_start = len(self.code)

        self.patch_jump(entry_jump, main_start)

        return {
            "code": self.code,
            "constants": self.constants,
            "strings": self.strings,
            "functions": self.functions,
            "classes": self.classes
        }

    def compile_function_body(self, node):
        # Arguments will be stored directly into local frame by VM.
        # Just compile the body statements.
        for stmt in node.body:
            self.compile_stmt(stmt)
        # Default return if the function finishes without returning explicitly
        self.emit(OpCode.LOAD_CONST, self.add_const(0))
        self.emit(OpCode.RETURN)

    def compile_stmt(self, node):
        if isinstance(node, Print):
            self.compile_expr(node.value)
            self.emit(OpCode.PRINT)
        elif isinstance(node, Assignment):
            self.compile_expr(node.value)
            self.emit(OpCode.STORE_NAME, node.name)
        elif isinstance(node, DataFieldAssign):
            # Evaluate value, then instance, then emit store_attr
            self.compile_expr(node.value)
            self.compile_expr(node.instance)
            self.emit(OpCode.STORE_ATTR, node.field_name)
        elif isinstance(node, LoadLib):
            self.emit(OpCode.LOAD_STR, self.add_string(node.lib_path))
            self.emit(OpCode.LOAD_LIB, node.alias)
        elif isinstance(node, Import):
            # Imports are handled in the pre-pass of compile(), skip here
            pass
        elif isinstance(node, IfElse):
            self.compile_expr(node.condition)
            jump_if_false = self.emit(OpCode.JUMP_IF_FALSE)

            for stmt in node.if_body:
                self.compile_stmt(stmt)

            jump_end = self.emit(OpCode.JUMP)

            self.patch_jump(jump_if_false, len(self.code))
            for stmt in node.else_body:
                self.compile_stmt(stmt)

            self.patch_jump(jump_end, len(self.code))

        elif isinstance(node, While):
            start_idx = len(self.code)

            self.compile_expr(node.condition)
            jump_end = self.emit(OpCode.JUMP_IF_FALSE)

            self.loop_stack.append((start_idx, []))

            for stmt in node.body:
                self.compile_stmt(stmt)

            self.emit(OpCode.JUMP, start_idx)
            self.patch_jump(jump_end, len(self.code))

            _, break_jumps = self.loop_stack.pop()
            for jump_idx in break_jumps:
                self.patch_jump(jump_idx, len(self.code))

        elif isinstance(node, Break):
            if self.loop_stack:
                idx = self.emit(OpCode.JUMP)
                self.loop_stack[-1][1].append(idx)
        elif isinstance(node, Continue):
            if self.loop_stack:
                start_idx = self.loop_stack[-1][0]
                self.emit(OpCode.JUMP, start_idx)
        elif isinstance(node, Return):
            self.compile_expr(node.value)
            self.emit(OpCode.RETURN)
        elif isinstance(node, RawBlock):
            for stmt in node.body:
                self.compile_stmt(stmt)
        elif isinstance(node, Export):
            # The VM dynamically looks up global functions and variables,
            # so `@export` doesn't strictly need a runtime compilation step in this simplified VM,
            # but we parse it to be complete.
            pass
        elif isinstance(node, Call): # Ignore standalone function call results
            self.compile_expr(node)
        elif isinstance(node, MethodCall):
            self.compile_expr(node)
        elif isinstance(node, Free):
            self.compile_expr(node.ptr)
            self.emit(OpCode.FREE)
        elif isinstance(node, WriteFile):
            self.compile_expr(node.fd)
            self.compile_expr(node.content)
            self.emit(OpCode.WRITE_FILE)
        elif isinstance(node, CloseFile):
            self.compile_expr(node.fd)
            self.emit(OpCode.CLOSE_FILE)
        elif isinstance(node, PointerAssign):
            if node.property == "value":
                self.compile_expr(node.value) # value to store
                self.compile_expr(node.ptr)   # pointer address
                self.emit(OpCode.STORE_PTR)
            else:
                raise Exception(f"Cannot assign to pointer property {node.property}")
        elif isinstance(node, ArrayIndexAssign):
            self.compile_expr(node.value)
            self.compile_expr(node.base)
            self.compile_expr(node.index)
            self.emit(OpCode.STORE_INDEX)
        elif isinstance(node, ForLoop):
            # for var_name = start to end step step { body }
            self.compile_expr(node.start)
            self.emit(OpCode.STORE_NAME, node.var_name)

            start_idx = len(self.code)
            self.loop_stack.append((start_idx, []))

            # Condition
            self.emit(OpCode.LOAD_NAME, node.var_name)
            self.compile_expr(node.end)
            if node.is_downto:
                self.emit(OpCode.CMP_GE)
            else:
                self.emit(OpCode.CMP_LE)

            jump_end = self.emit(OpCode.JUMP_IF_FALSE)

            for stmt in node.body:
                self.compile_stmt(stmt)

            # Step
            self.emit(OpCode.LOAD_NAME, node.var_name)
            self.compile_expr(node.step)
            if node.is_downto:
                self.emit(OpCode.SUB)
            else:
                self.emit(OpCode.ADD)
            self.emit(OpCode.STORE_NAME, node.var_name)

            self.emit(OpCode.JUMP, start_idx)
            self.patch_jump(jump_end, len(self.code))

            _, break_jumps = self.loop_stack.pop()
            for jump_idx in break_jumps:
                self.patch_jump(jump_idx, len(self.code))
        elif isinstance(node, Data):
            # Data definitions are handled in the first pass metadata collection
            pass
        elif isinstance(node, Try):
            catch_label = self.emit(OpCode.PUSH_HANDLER)
            for stmt in node.body:
                self.compile_stmt(stmt)
            self.emit(OpCode.POP_HANDLER)
            end_label = self.emit(OpCode.JUMP)
            self.patch_jump(catch_label, len(self.code))
            self.emit(OpCode.STORE_NAME, node.catch_var)
            for stmt in node.catch_body:
                self.compile_stmt(stmt)
            self.patch_jump(end_label, len(self.code))
        elif isinstance(node, Throw):
            self.compile_expr(node.value)
            self.emit(OpCode.THROW)

    def compile_expr(self, node):
        if isinstance(node, Number):
            self.emit(OpCode.LOAD_CONST, self.add_const(node.value))
        elif isinstance(node, String):
            self.emit(OpCode.LOAD_STR, self.add_string(node.value))
        elif isinstance(node, Boolean):
            self.emit(OpCode.LOAD_BOOL, node.value)
        elif isinstance(node, Variable):
            self.emit(OpCode.LOAD_NAME, node.name)
        elif isinstance(node, Self):
            self.emit(OpCode.LOAD_SELF)
        elif isinstance(node, UnaryOp):
            self.compile_expr(node.value)
            if node.op == "-":
                # To do negative, we load 0, load expr, SUB. Or we can just LOAD_CONST -1 and MUL. 
                # Let's LOAD_CONST -1 and MUL!
                self.emit(OpCode.LOAD_CONST, self.add_const(-1))
                self.emit(OpCode.MUL)
            elif node.op == "not":
                self.emit(OpCode.NOT)
            elif node.op == "~":
                self.emit(OpCode.BIT_NOT)
        elif isinstance(node, BinOp):
            self.compile_expr(node.left)
            self.compile_expr(node.right)
            ops = {
                "+": OpCode.ADD, "-": OpCode.SUB,
                "*": OpCode.MUL, "/": OpCode.DIV,
                "%": OpCode.MOD,
                "and": OpCode.AND, "or": OpCode.OR,
                "&": OpCode.BIT_AND, "|": OpCode.BIT_OR, "^": OpCode.BIT_XOR,
                "<<": OpCode.SHL, ">>": OpCode.SAR
            }
            self.emit(ops[node.op])
        elif isinstance(node, Compare):
            self.compile_expr(node.left)
            self.compile_expr(node.right)
            ops = {
                "==": OpCode.CMP_EQ, "!=": OpCode.CMP_NEQ,
                "<": OpCode.CMP_LT, ">": OpCode.CMP_GT,
                "<=": OpCode.CMP_LE, ">=": OpCode.CMP_GE,
                "has": OpCode.HAS
            }
            self.emit(ops[node.op])
        elif isinstance(node, SizeOf):
            self.compile_expr(node.target)
            self.emit(OpCode.SIZEOF)
        elif isinstance(node, Len):
            self.compile_expr(node.target)
            self.emit(OpCode.LEN)
        elif isinstance(node, OpenFile):
            self.compile_expr(node.path)
            self.compile_expr(node.mode)
            self.emit(OpCode.OPEN_FILE)
        elif isinstance(node, ReadFile):
            self.compile_expr(node.fd)
            self.emit(OpCode.READ_FILE)
        elif isinstance(node, DataFieldAccess):
            if isinstance(node.instance, Variable):
                # We need to distinguish between global instances and `this` at compile time
                pass
            self.compile_expr(node.instance)
            self.emit(OpCode.LOAD_ATTR, node.field_name)
        elif isinstance(node, MethodCall):
            for arg in node.args:
                self.compile_expr(arg)
            self.compile_expr(node.instance)
            self.emit(OpCode.CALL_METHOD, (node.method_name, len(node.args)))
        elif isinstance(node, Call):
            for arg in node.args:
                self.compile_expr(arg)

            # If the name has a dot, it might be an FFI call `libc.printf`
            if "." in node.name:
                lib_name, func_name = node.name.split(".", 1)
                self.emit(OpCode.CALL_LIB, (lib_name, func_name, len(node.args)))
            else:
                self.emit(OpCode.CALL, (node.name, len(node.args)))
        elif isinstance(node, DataInstance):
            # DataInstance(data_name) represents creating a raw struct
            self.emit(OpCode.NEW, (node.data_name, 0))
        elif isinstance(node, Alloc):
            self.compile_expr(node.size)
            self.emit(OpCode.ALLOC)
        elif isinstance(node, ArrayIndex):
            self.compile_expr(node.base)
            self.compile_expr(node.index)
            self.emit(OpCode.LOAD_INDEX)
        elif isinstance(node, Slice):
            self.compile_expr(node.base)
            if node.start:
                self.compile_expr(node.start)
            else:
                self.emit(OpCode.LOAD_CONST, self.add_const(0))
            if node.end:
                self.compile_expr(node.end)
            else:
                self.emit(OpCode.LOAD_CONST, self.add_const(-1))
            self.emit(OpCode.SLICE)
        elif isinstance(node, PointerProperty):
            self.compile_expr(node.ptr)
            if node.property == "value":
                self.emit(OpCode.LOAD_PTR)
            elif node.property == "addr":
                pass # Already top of stack
            else:
                raise Exception(f"Pointer property {node.property} not yet implemented in VM")
        elif isinstance(node, StrConvert):
            self.compile_expr(node.target)
            self.emit(OpCode.STR_CONVERT)
        elif isinstance(node, ListLiteral):
            for el in node.elements:
                self.compile_expr(el)
            self.emit(OpCode.NEW_LIST, len(node.elements))
        elif isinstance(node, DictLiteral):
            for k, v in zip(node.keys, node.values):
                self.compile_expr(v)
                self.compile_expr(k)
            self.emit(OpCode.BUILD_DICT, len(node.keys))
        elif isinstance(node, Block):
            for stmt in node.stmts[:-1]:
                self.compile_stmt(stmt)
            self.compile_expr(node.stmts[-1])
        else:
            raise Exception(f"Compiler unhandled expr: {type(node)}")
