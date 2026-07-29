"""Custom Virtual Machine to execute Nova bytecode"""

import struct
import ctypes
import os
from .opcodes import OpCode

class Instance:
    def __init__(self, class_name):
        self.class_name = class_name
        self.fields = {}
        self.ref_count = 0

class Frame:
    def __init__(self, return_address, local_env, self_context=None, is_init=False, pending_action=None, handler_depth=0):
        self.return_address = return_address
        self.locals = local_env.copy() if local_env else {}
        self.self_context = self_context
        self.is_init = is_init
        self.pending_action = pending_action
        self.handler_depth = handler_depth

class VirtualMachine:
    def __init__(self, program):
        self.code = program["code"]
        self.constants = program["constants"]
        self.strings = program["strings"]
        self.functions = program["functions"]
        self.classes = program["classes"]
        self.stack = []
        self.frames = []
        self.env = {}
        self.ip = 0
        self.heap = bytearray(1024 * 1024)
        self.heap_ptr = 1
        self.allocations = {}
        self.libraries = {}
        self.open_files = {}
        self.next_fd = 1
        self.handler_stack = []

    def retain(self, obj):
        if isinstance(obj, Instance):
            obj.ref_count += 1

    def release(self, obj):
        if isinstance(obj, Instance):
            obj.ref_count -= 1
            if obj.ref_count <= 0:
                for val in obj.fields.values():
                    self.release(val)

    def _to_str(self, val):
        if isinstance(val, bytearray):
            return val.decode('utf-8')
        return str(val)

    def _to_bytes(self, val):
        return bytearray(self._to_str(val).encode('utf-8'))

    def _call_builtin(self, func_name, args):
        handler = _STRING_HANDLERS.get(func_name)
        if handler:
            handler(self, args)
            return True
        handler = _BUILTIN_HANDLERS.get(func_name)
        if handler:
            handler(self, args)
            return True
        return False

# --- Opcode dispatch handlers (module-level for speed) ---

def _op_noop(vm, arg):
    pass

def _op_load_const(vm, arg):
    vm.stack.append(vm.constants[arg])

def _op_load_str(vm, arg):
    vm.stack.append(bytearray(vm.strings[arg].encode('utf-8')))

def _op_load_bool(vm, arg):
    vm.stack.append(arg)

def _op_load_name(vm, arg):
    name = arg
    if vm.frames and name in vm.frames[-1].locals:
        vm.stack.append(vm.frames[-1].locals[name])
    elif name in vm.env:
        vm.stack.append(vm.env[name])
    else:
        vm.stack.append(0)

def _op_store_name(vm, arg):
    val = vm.stack.pop()
    if vm.frames:
        old_val = vm.frames[-1].locals.get(arg)
        vm.release(old_val)
        vm.retain(val)
        vm.frames[-1].locals[arg] = val
    else:
        old_val = vm.env.get(arg)
        vm.release(old_val)
        vm.retain(val)
        vm.env[arg] = val

def _op_add(vm, arg):
    b = vm.stack.pop()
    a = vm.stack.pop()
    if isinstance(a, Instance):
        method_name = f"{a.class_name}.__add__"
        if method_name in vm.functions:
            func_meta = vm.functions[method_name]
            local_env = {}
            params = func_meta["params"]
            if len(params) > 0:
                p = params[0][0] if isinstance(params[0], (list, tuple)) else params[0]
                local_env[p] = b
            vm.frames.append(Frame(vm.ip, local_env, self_context=a, handler_depth=len(vm.handler_stack)))
            vm.ip = func_meta["ip"]
            return
    if isinstance(a, bytearray) and not isinstance(b, bytearray):
        b = bytearray(str(b).encode('utf-8'))
    elif isinstance(b, bytearray) and not isinstance(a, bytearray):
        a = bytearray(str(a).encode('utf-8'))
    vm.stack.append(a + b)

def _op_sub(vm, arg):
    b = vm.stack.pop()
    a = vm.stack.pop()
    if isinstance(a, Instance):
        method_name = f"{a.class_name}.__sub__"
        if method_name in vm.functions:
            func_meta = vm.functions[method_name]
            local_env = {}
            params = func_meta["params"]
            if len(params) > 0:
                p = params[0][0] if isinstance(params[0], (list, tuple)) else params[0]
                local_env[p] = b
            vm.frames.append(Frame(vm.ip, local_env, self_context=a, handler_depth=len(vm.handler_stack)))
            vm.ip = func_meta["ip"]
            return
    vm.stack.append(a - b)

def _op_mul(vm, arg):
    b = vm.stack.pop()
    a = vm.stack.pop()
    if isinstance(a, Instance):
        method_name = f"{a.class_name}.__mul__"
        if method_name in vm.functions:
            func_meta = vm.functions[method_name]
            local_env = {}
            params = func_meta["params"]
            if len(params) > 0:
                p = params[0][0] if isinstance(params[0], (list, tuple)) else params[0]
                local_env[p] = b
            vm.frames.append(Frame(vm.ip, local_env, self_context=a, handler_depth=len(vm.handler_stack)))
            vm.ip = func_meta["ip"]
            return
    vm.stack.append(a * b)

def _op_div(vm, arg):
    b = vm.stack.pop()
    a = vm.stack.pop()
    if isinstance(a, int) and isinstance(b, int):
        vm.stack.append(a // b)
    else:
        vm.stack.append(a / b)

def _op_mod(vm, arg):
    b = vm.stack.pop()
    a = vm.stack.pop()
    vm.stack.append(a % b)

def _op_cmp_eq(vm, arg):
    b = vm.stack.pop()
    a = vm.stack.pop()
    if isinstance(a, Instance):
        method_name = f"{a.class_name}.__eq__"
        if method_name in vm.functions:
            func_meta = vm.functions[method_name]
            local_env = {}
            params = func_meta["params"]
            if len(params) > 0:
                p = params[0][0] if isinstance(params[0], (list, tuple)) else params[0]
                local_env[p] = b
            vm.frames.append(Frame(vm.ip, local_env, self_context=a, handler_depth=len(vm.handler_stack)))
            vm.ip = func_meta["ip"]
            return
    vm.stack.append(a == b)

def _op_cmp_lt(vm, arg):
    b = vm.stack.pop(); a = vm.stack.pop(); vm.stack.append(a < b)

def _op_cmp_le(vm, arg):
    b = vm.stack.pop(); a = vm.stack.pop(); vm.stack.append(a <= b)

def _op_cmp_gt(vm, arg):
    b = vm.stack.pop(); a = vm.stack.pop(); vm.stack.append(a > b)

def _op_cmp_ge(vm, arg):
    b = vm.stack.pop(); a = vm.stack.pop(); vm.stack.append(a >= b)

def _op_cmp_neq(vm, arg):
    b = vm.stack.pop(); a = vm.stack.pop(); vm.stack.append(a != b)

def _op_and(vm, arg):
    b = vm.stack.pop(); a = vm.stack.pop(); vm.stack.append(a and b)

def _op_or(vm, arg):
    b = vm.stack.pop(); a = vm.stack.pop(); vm.stack.append(a or b)

def _op_bit_and(vm, arg):
    b = vm.stack.pop(); a = vm.stack.pop(); vm.stack.append(a & b)

def _op_bit_or(vm, arg):
    b = vm.stack.pop(); a = vm.stack.pop(); vm.stack.append(a | b)

def _op_bit_xor(vm, arg):
    b = vm.stack.pop(); a = vm.stack.pop(); vm.stack.append(a ^ b)

def _op_bit_not(vm, arg):
    a = vm.stack.pop(); vm.stack.append(~a)

def _op_shl(vm, arg):
    b = vm.stack.pop(); a = vm.stack.pop(); vm.stack.append(a << b)

def _op_sar(vm, arg):
    b = vm.stack.pop(); a = vm.stack.pop(); vm.stack.append(a >> b)

def _op_has(vm, arg):
    b = vm.stack.pop(); a = vm.stack.pop(); vm.stack.append(b in a)

def _op_not(vm, arg):
    a = vm.stack.pop(); vm.stack.append(not a)

def _op_push_handler(vm, arg):
    vm.handler_stack.append((arg, len(vm.stack)))

def _op_pop_handler(vm, arg):
    if vm.handler_stack:
        vm.handler_stack.pop()

def _op_throw(vm, arg):
    exc_val = vm.stack.pop()
    if not vm.handler_stack:
        print(f"Unhandled exception: {exc_val}")
        vm.ip = len(vm.code)
        return
    catch_ip, saved_sp = vm.handler_stack.pop()
    del vm.stack[saved_sp:]
    vm.stack.append(exc_val)
    vm.ip = catch_ip

def _op_jump(vm, arg):
    vm.ip = arg

def _op_jump_if_false(vm, arg):
    cond = vm.stack.pop()
    if not cond:
        vm.ip = arg

def _op_print(vm, arg):
    val = vm.stack.pop()
    if isinstance(val, Instance):
        method_name = f"{val.class_name}.__str__"
        if method_name in vm.functions:
            func_meta = vm.functions[method_name]
            vm.frames.append(Frame(vm.ip, {}, self_context=val, pending_action='print', handler_depth=len(vm.handler_stack)))
            vm.ip = func_meta["ip"]
            return
        else:
            print(f"<{val.class_name} instance>")
    elif isinstance(val, bytearray):
        print(val.decode('utf-8'))
    else:
        print(val)

def _op_alloc(vm, arg):
    size = vm.stack.pop()
    ptr = vm.heap_ptr
    vm.heap_ptr += size
    vm.allocations[ptr] = size
    vm.stack.append(ptr)

def _op_free(vm, arg):
    ptr = vm.stack.pop()
    if ptr in vm.allocations:
        del vm.allocations[ptr]

def _op_store_ptr(vm, arg):
    ptr = vm.stack.pop(); val = vm.stack.pop()
    struct.pack_into("<i", vm.heap, ptr, val)

def _op_load_ptr(vm, arg):
    ptr = vm.stack.pop()
    val = struct.unpack_from("<i", vm.heap, ptr)[0]
    vm.stack.append(val)

def _op_load_index(vm, arg):
    index = vm.stack.pop(); base = vm.stack.pop()
    if isinstance(base, bytearray):
        vm.stack.append(bytearray([base[index]]))
    elif isinstance(base, dict):
        if isinstance(index, bytearray):
            index = index.decode('utf-8')
        if index not in base:
            raise Exception(f"KeyError: {index} not found in dictionary")
        vm.stack.append(base[index])
    else:
        vm.stack.append(base[index])

def _op_store_index(vm, arg):
    index = vm.stack.pop(); base = vm.stack.pop(); val = vm.stack.pop()
    if isinstance(base, bytearray):
        if isinstance(val, str):
            if len(val) != 1:
                raise Exception("ValueError: can only assign single character string to bytearray index")
            base[index] = ord(val)
        elif isinstance(val, bytearray):
            if len(val) != 1:
                raise Exception("ValueError: can only assign single character string to bytearray index")
            base[index] = val[0]
        else:
            base[index] = val
    elif isinstance(base, dict):
        if isinstance(index, bytearray):
            index = index.decode('utf-8')
        base[index] = val
    else:
        base[index] = val

def _op_new_list(vm, arg):
    elements = []
    for _ in range(arg):
        elements.append(vm.stack.pop())
    elements.reverse()
    vm.stack.append(elements)

def _op_build_dict(vm, arg):
    d = {}
    for _ in range(arg):
        k = vm.stack.pop(); v = vm.stack.pop()
        if isinstance(k, bytearray):
            k = k.decode('utf-8')
        d[k] = v
    vm.stack.append(d)

def _op_sizeof(vm, arg):
    val = vm.stack.pop()
    if isinstance(val, int) and val in vm.allocations:
        vm.stack.append(vm.allocations[val])
    elif isinstance(val, int):
        vm.stack.append(4)
    elif isinstance(val, str):
        vm.stack.append(len(val))
    elif isinstance(val, Instance):
        vm.stack.append(len(val.fields) * 4)
    else:
        vm.stack.append(4)

def _op_len(vm, arg):
    val = vm.stack.pop()
    if isinstance(val, Instance):
        method_name = f"{val.class_name}.__len__"
        if method_name in vm.functions:
            func_meta = vm.functions[method_name]
            vm.frames.append(Frame(vm.ip, {}, self_context=val, handler_depth=len(vm.handler_stack)))
            vm.ip = func_meta["ip"]
            return
        else:
            raise Exception(f"len() not defined for {val.class_name}")
    elif isinstance(val, (str, bytearray, list, dict)):
        vm.stack.append(len(val))
    else:
        raise Exception("len() applied to invalid type")

def _op_open_file(vm, arg):
    mode_val = vm.stack.pop(); path_val = vm.stack.pop()
    mode = mode_val.decode('utf-8') if isinstance(mode_val, bytearray) else mode_val
    path = path_val.decode('utf-8') if isinstance(path_val, bytearray) else path_val
    try:
        f = open(path, mode)
        fd = vm.next_fd
        vm.open_files[fd] = f
        vm.next_fd += 1
        vm.stack.append(fd)
    except Exception as e:
        print(f"Error opening file: {e}")
        vm.stack.append(0)

def _op_read_file(vm, arg):
    fd = vm.stack.pop()
    if fd in vm.open_files:
        content = vm.open_files[fd].read()
        vm.stack.append(bytearray(content.encode('utf-8')))
    else:
        vm.stack.append(bytearray(b""))

def _op_write_file(vm, arg):
    content_val = vm.stack.pop(); fd = vm.stack.pop()
    content = content_val.decode('utf-8') if isinstance(content_val, bytearray) else content_val
    if fd in vm.open_files:
        vm.open_files[fd].write(str(content))

def _op_close_file(vm, arg):
    fd = vm.stack.pop()
    if fd in vm.open_files:
        vm.open_files[fd].close()
        del vm.open_files[fd]

def _op_new(vm, arg):
    class_name, num_args = arg
    args = [vm.stack.pop() for _ in range(num_args)]
    args.reverse()
    vm.stack.append(Instance(class_name))

def _op_load_attr(vm, arg):
    prop = arg; instance = vm.stack.pop()
    if not isinstance(instance, Instance):
        raise Exception("Property access on non-object")
    vm.stack.append(instance.fields.get(prop, 0))

def _op_store_attr(vm, arg):
    prop = arg; instance = vm.stack.pop(); val = vm.stack.pop()
    if not isinstance(instance, Instance):
        raise Exception("Property assign on non-object")
    old_val = instance.fields.get(prop)
    vm.release(old_val)
    vm.retain(val)
    instance.fields[prop] = val

def _op_load_self(vm, arg):
    if vm.frames and vm.frames[-1].self_context:
        vm.stack.append(vm.frames[-1].self_context)
    else:
        raise Exception("Used 'self' outside of an instance method")

def _op_call_method(vm, arg):
    method_name, num_args = arg
    instance = vm.stack.pop()
    args = [vm.stack.pop() for _ in range(num_args)]
    args.reverse()
    if isinstance(instance, int) and instance == 0:
        raise Exception("Attempted method call on null/uninitialized variable")
    if isinstance(instance, str) and instance in vm.libraries:
        lib = vm.libraries[instance]
        try:
            func = getattr(lib, method_name)
        except AttributeError:
            raise Exception(f"Function {method_name} not found in library {instance}")
        ctypes_args = []
        for a in args:
            if isinstance(a, str):
                ctypes_args.append(a.encode('utf-8'))
            elif isinstance(a, bytearray):
                ctypes_args.append(bytes(a))
            elif isinstance(a, int):
                ctypes_args.append(ctypes.c_int(a))
            elif isinstance(a, float):
                ctypes_args.append(ctypes.c_double(a))
            else:
                ctypes_args.append(a)
        result = func(*ctypes_args)
        vm.stack.append(result)
        return
    if isinstance(instance, list):
        if method_name == "append":
            instance.append(args[0]); vm.stack.append(0)
        elif method_name == "pop":
            vm.stack.append(instance.pop() if len(instance) > 0 else 0)
        elif method_name == "insert":
            instance.insert(args[0], args[1]); vm.stack.append(0)
        elif method_name == "clear":
            instance.clear(); vm.stack.append(0)
        else:
            raise Exception(f"List method {method_name} not supported")
        return
    if isinstance(instance, dict):
        if method_name == "has":
            k = args[0]
            if isinstance(k, bytearray): k = k.decode('utf-8')
            vm.stack.append(k in instance)
        elif method_name == "get":
            k = args[0]
            if isinstance(k, bytearray): k = k.decode('utf-8')
            vm.stack.append(instance.get(k, 0))
        elif method_name == "set":
            k = args[0]
            if isinstance(k, bytearray): k = k.decode('utf-8')
            instance[k] = args[1]; vm.stack.append(0)
        elif method_name == "remove":
            k = args[0]
            if isinstance(k, bytearray): k = k.decode('utf-8')
            if k in instance: del instance[k]
            vm.stack.append(0)
        elif method_name == "keys":
            keys = [bytearray(k.encode('utf-8')) if isinstance(k, str) else k for k in instance.keys()]
            vm.stack.append(keys)
        elif method_name == "values":
            vm.stack.append(list(instance.values()))
        elif method_name == "items":
            items = []
            for k, v in instance.items():
                items.append(bytearray(k.encode('utf-8')) if isinstance(k, str) else k)
                items.append(v)
            vm.stack.append(items)
        else:
            raise Exception(f"Dict method {method_name} not supported")
        return
    full_name = f"{instance.class_name}.{method_name}"
    if full_name not in vm.functions:
        raise Exception(f"Method {full_name} not found")
    func_meta = vm.functions[full_name]
    local_env = {}
    for i, param in enumerate(func_meta["params"]):
        param_name = param[0] if isinstance(param, (list, tuple)) else param
        local_env[param_name] = args[i] if i < len(args) else 0
    vm.frames.append(Frame(vm.ip, local_env, self_context=instance, handler_depth=len(vm.handler_stack)))
    vm.ip = func_meta["ip"]

def _op_load_lib(vm, arg):
    lib_path = vm.stack.pop()
    if isinstance(lib_path, bytearray):
        lib_path = lib_path.decode('utf-8')
    alias = arg
    try:
        lib = ctypes.CDLL(lib_path)
        vm.libraries[alias] = lib
    except Exception as e:
        if os.name != 'nt':
            try:
                lib = ctypes.CDLL(f"lib{lib_path}.so.6")
                vm.libraries[alias] = lib
            except:
                raise Exception(f"Failed to load FFI library {lib_path}: {str(e)}")
        else:
            raise Exception(f"Failed to load FFI library {lib_path}: {str(e)}")
    vm.env[alias] = alias

def _op_call_lib(vm, arg):
    lib_name, func_name, num_args = arg
    args = [vm.stack.pop() for _ in range(num_args)]
    args.reverse()
    if lib_name not in vm.libraries:
        raise Exception(f"FFI Library not loaded: {lib_name}")
    lib = vm.libraries[lib_name]
    try:
        func = getattr(lib, func_name)
    except AttributeError:
        raise Exception(f"Function {func_name} not found in library {lib_name}")
    ctypes_args = []
    for a in args:
        if isinstance(a, str):
            ctypes_args.append(a.encode('utf-8'))
        elif isinstance(a, bytearray):
            ctypes_args.append(bytes(a))
        elif isinstance(a, int):
            ctypes_args.append(ctypes.c_int(a))
        elif isinstance(a, float):
            ctypes_args.append(ctypes.c_double(a))
        else:
            ctypes_args.append(a)
    result = func(*ctypes_args)
    vm.stack.append(result)

def _op_slice(vm, arg):
    end = vm.stack.pop(); start = vm.stack.pop(); base = vm.stack.pop()
    if end == -1:
        end = len(base)
    if isinstance(base, bytearray):
        vm.stack.append(bytearray(base[start:end]))
    elif isinstance(base, list):
        vm.stack.append(base[start:end])
    else:
        raise Exception(f"Slice not supported for type {type(base)}")

def _op_str_convert(vm, arg):
    val = vm.stack.pop()
    if isinstance(val, Instance):
        method_name = f"{val.class_name}.__str__"
        if method_name in vm.functions:
            func_meta = vm.functions[method_name]
            vm.frames.append(Frame(vm.ip, {}, self_context=val, handler_depth=len(vm.handler_stack)))
            vm.ip = func_meta["ip"]
            return
        else:
            vm.stack.append(bytearray(f"<{val.class_name} instance>".encode('utf-8')))
    elif isinstance(val, bytearray):
        vm.stack.append(val)
    elif isinstance(val, bool):
        vm.stack.append(bytearray(str(val).lower().encode('utf-8')))
    else:
        vm.stack.append(bytearray(str(val).encode('utf-8')))

def _op_call(vm, arg):
    func_name, num_args = arg
    args = [vm.stack.pop() for _ in range(num_args)]
    args.reverse()
    if func_name in vm.classes:
        instance = Instance(func_name)
        init_name = f"{func_name}.__init__"
        if init_name in vm.functions:
            func_meta = vm.functions[init_name]
            local_env = {}
            for i, param in enumerate(func_meta["params"]):
                param_name = param[0] if isinstance(param, (list, tuple)) else param
                local_env[param_name] = args[i] if i < len(args) else 0
            vm.stack.append(instance)
            vm.frames.append(Frame(vm.ip, local_env, self_context=instance, is_init=True, handler_depth=len(vm.handler_stack)))
            vm.ip = func_meta["ip"]
        else:
            vm.stack.append(instance)
        return
    if func_name not in vm.functions:
        if vm._call_builtin(func_name, args):
            return
        raise Exception(f"Function {func_name} not found")
    func_meta = vm.functions[func_name]
    local_env = {}
    for i, param in enumerate(func_meta["params"]):
        param_name = param[0] if isinstance(param, (list, tuple)) else param
        local_env[param_name] = args[i] if i < len(args) else 0
    vm.frames.append(Frame(vm.ip, local_env, handler_depth=len(vm.handler_stack)))
    vm.ip = func_meta["ip"]

def _op_return(vm, arg):
    if vm.frames:
        frame = vm.frames.pop()
        del vm.handler_stack[frame.handler_depth:]
        for val in frame.locals.values():
            vm.release(val)
        if frame.is_init:
            vm.stack.pop()
        if frame.pending_action == 'print':
            ret_val = vm.stack.pop()
            if isinstance(ret_val, bytearray):
                print(ret_val.decode('utf-8'))
            else:
                print(ret_val)
        vm.ip = frame.return_address
    else:
        vm.ip = len(vm.code)

_OPCODE_DISPATCH = {
    OpCode.LOAD_CONST: _op_load_const,
    OpCode.LOAD_STR: _op_load_str,
    OpCode.LOAD_BOOL: _op_load_bool,
    OpCode.LOAD_NAME: _op_load_name,
    OpCode.STORE_NAME: _op_store_name,
    OpCode.ADD: _op_add,
    OpCode.SUB: _op_sub,
    OpCode.MUL: _op_mul,
    OpCode.DIV: _op_div,
    OpCode.MOD: _op_mod,
    OpCode.CMP_EQ: _op_cmp_eq,
    OpCode.CMP_LT: _op_cmp_lt,
    OpCode.CMP_LE: _op_cmp_le,
    OpCode.CMP_GT: _op_cmp_gt,
    OpCode.CMP_GE: _op_cmp_ge,
    OpCode.CMP_NEQ: _op_cmp_neq,
    OpCode.AND: _op_and,
    OpCode.OR: _op_or,
    OpCode.BIT_AND: _op_bit_and,
    OpCode.BIT_OR: _op_bit_or,
    OpCode.BIT_XOR: _op_bit_xor,
    OpCode.BIT_NOT: _op_bit_not,
    OpCode.SHL: _op_shl,
    OpCode.SAR: _op_sar,
    OpCode.HAS: _op_has,
    OpCode.NOT: _op_not,
    OpCode.PUSH_HANDLER: _op_push_handler,
    OpCode.POP_HANDLER: _op_pop_handler,
    OpCode.THROW: _op_throw,
    OpCode.JUMP: _op_jump,
    OpCode.JUMP_IF_FALSE: _op_jump_if_false,
    OpCode.PRINT: _op_print,
    OpCode.ALLOC: _op_alloc,
    OpCode.FREE: _op_free,
    OpCode.STORE_PTR: _op_store_ptr,
    OpCode.LOAD_PTR: _op_load_ptr,
    OpCode.LOAD_INDEX: _op_load_index,
    OpCode.STORE_INDEX: _op_store_index,
    OpCode.NEW_LIST: _op_new_list,
    OpCode.BUILD_DICT: _op_build_dict,
    OpCode.SIZEOF: _op_sizeof,
    OpCode.LEN: _op_len,
    OpCode.OPEN_FILE: _op_open_file,
    OpCode.READ_FILE: _op_read_file,
    OpCode.WRITE_FILE: _op_write_file,
    OpCode.CLOSE_FILE: _op_close_file,
    OpCode.NEW: _op_new,
    OpCode.LOAD_ATTR: _op_load_attr,
    OpCode.STORE_ATTR: _op_store_attr,
    OpCode.LOAD_SELF: _op_load_self,
    OpCode.CALL_METHOD: _op_call_method,
    OpCode.LOAD_LIB: _op_load_lib,
    OpCode.CALL_LIB: _op_call_lib,
    OpCode.SLICE: _op_slice,
    OpCode.STR_CONVERT: _op_str_convert,
    OpCode.CALL: _op_call,
    OpCode.RETURN: _op_return,
}

def _vm_run(self):
    while self.ip < len(self.code):
        opcode, arg = self.code[self.ip]
        self.ip += 1
        handler = _OPCODE_DISPATCH.get(opcode)
        if handler:
            handler(self, arg)
        else:
            raise Exception(f"Unknown opcode: {opcode}")

VirtualMachine.run = _vm_run

def _string_split(m, args):
    s = m._to_str(args[0])
    delim = m._to_str(args[1]) if len(args) > 1 else " "
    m.stack.append([bytearray(p.encode('utf-8')) for p in s.split(delim)])

def _string_join(m, args):
    lst = args[0]
    delim = m._to_str(args[1]) if len(args) > 1 else ""
    m.stack.append(bytearray(delim.join(m._to_str(x) for x in lst).encode('utf-8')))

def _string_trim(m, args):
    m.stack.append(bytearray(m._to_str(args[0]).strip().encode('utf-8')))

def _string_contains(m, args):
    m.stack.append(1 if m._to_str(args[1]) in m._to_str(args[0]) else 0)

def _string_replace(m, args):
    s = m._to_str(args[0])
    old = m._to_str(args[1]) if len(args) > 1 else ""
    new = m._to_str(args[2]) if len(args) > 2 else ""
    m.stack.append(bytearray(s.replace(old, new).encode('utf-8')))

def _string_to_upper(m, args):
    m.stack.append(bytearray(m._to_str(args[0]).upper().encode('utf-8')))

def _string_to_lower(m, args):
    m.stack.append(bytearray(m._to_str(args[0]).lower().encode('utf-8')))

def _string_starts_with(m, args):
    m.stack.append(1 if m._to_str(args[0]).startswith(m._to_str(args[1])) else 0)

def _string_ends_with(m, args):
    m.stack.append(1 if m._to_str(args[0]).endswith(m._to_str(args[1])) else 0)

_STRING_HANDLERS = {
    "split": _string_split,
    "join": _string_join,
    "trim": _string_trim,
    "contains": _string_contains,
    "replace": _string_replace,
    "to_upper": _string_to_upper,
    "to_lower": _string_to_lower,
    "starts_with": _string_starts_with,
    "ends_with": _string_ends_with,
}

# === Built-in function handlers (for the VM interpreter) ===

def _builtin_abs(m, args):
    m.stack.append(abs(args[0]))

def _builtin_min(m, args):
    m.stack.append(min(args[0], args[1]))

def _builtin_max(m, args):
    m.stack.append(max(args[0], args[1]))

def _builtin_now(m, args):
    import datetime
    m.stack.append(bytearray(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S").encode('utf-8')))

def _builtin_call(m, args):
    """call(name: string, args_list: list) -> any
    Dynamically look up a Nova function by name and call it with the given args.
    The return value is left on the VM stack."""
    func_name = m._to_str(args[0])
    call_args = args[1] if len(args) > 1 else []

    if func_name not in m.functions:
        if not m._call_builtin(func_name, call_args):
            raise Exception(f"call(): function '{func_name}' not found")
        return

    func_meta = m.functions[func_name]
    local_env = {}
    for i, param in enumerate(func_meta["params"]):
        param_name = param[0] if isinstance(param, (list, tuple)) else param
        local_env[param_name] = call_args[i] if i < len(call_args) else 0

    m.frames.append(Frame(m.ip, local_env, handler_depth=len(m.handler_stack)))
    m.ip = func_meta["ip"]

def _builtin_type(m, args):
    val = args[0]
    if isinstance(val, Instance):
        m.stack.append(bytearray(b"data:" + val.class_name.encode('utf-8')))
    elif isinstance(val, bytearray):
        m.stack.append(bytearray(b"string"))
    elif isinstance(val, bool):
        m.stack.append(bytearray(b"bool"))
    elif isinstance(val, int):
        m.stack.append(bytearray(b"int"))
    elif isinstance(val, float):
        m.stack.append(bytearray(b"float"))
    elif isinstance(val, list):
        m.stack.append(bytearray(b"list"))
    elif isinstance(val, dict):
        m.stack.append(bytearray(b"dict"))
    else:
        m.stack.append(bytearray(b"unknown"))

def _builtin_file_exists(m, args):
    import os
    m.stack.append(1 if os.path.exists(m._to_str(args[0])) else 0)

def _builtin_file_size(m, args):
    import os
    path = m._to_str(args[0])
    try:
        m.stack.append(os.path.getsize(path))
    except:
        m.stack.append(0)

def _builtin_file_type(m, args):
    import os
    path = m._to_str(args[0])
    if os.path.isdir(path):
        m.stack.append(bytearray(b"dir"))
    elif os.path.isfile(path):
        m.stack.append(bytearray(b"file"))
    else:
        m.stack.append(bytearray(b""))

_BUILTIN_HANDLERS = {
    "type": _builtin_type,
    "call": _builtin_call,
    "abs": _builtin_abs,
    "min": _builtin_min,
    "max": _builtin_max,
    "now": _builtin_now,
    "file_exists": _builtin_file_exists,
    "file_size": _builtin_file_size,
    "file_type": _builtin_file_type,
}