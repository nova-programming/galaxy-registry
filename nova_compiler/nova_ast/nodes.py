"""Abstract Syntax Tree node definitions with pointer support"""

class Number:
    def __init__(self, value, line=0):
        self.line = line
        self.value = value
    def __repr__(self):
        return f"Number({self.value})"

class String:
    def __init__(self, value, line=0):
        self.line = line
        self.value = value
    def __repr__(self):
        return f"String({self.value})"

class Boolean:
    def __init__(self, value, line=0):
        self.line = line
        self.value = value
    def __repr__(self):
        return f"Boolean({self.value})"

class Variable:
    def __init__(self, name, type_name=None, line=0):
        self.line = line
        self.name = name
        self.type_name = type_name
    def __repr__(self):
        return f"Variable({self.name}, {self.type_name})"

class UnaryOp:
    def __init__(self, op, value, line=0):
        self.line = line
        self.op = op
        self.value = value
    def __repr__(self):
        return f"UnaryOp('{self.op}', {self.value})"

class BinOp:
    def __init__(self, left, op, right, line=0):
        self.line = line
        self.left = left
        self.op = op
        self.right = right
    def __repr__(self):
        return f"BinOp({self.left}, '{self.op}', {self.right})"

class Compare:
    def __init__(self, left, op, right, line=0):
        self.line = line
        self.left = left
        self.op = op
        self.right = right
    def __repr__(self):
        return f"Compare({self.left}, '{self.op}', {self.right})"

class Assignment:
    def __init__(self, name, value, type_name=None, is_const=False, line=0):
        self.line = line
        self.name = name
        self.value = value
        self.type_name = type_name
        self.is_const = is_const
    def __repr__(self):
        return f"Assignment('{self.name}', {self.value}, type={self.type_name}, const={self.is_const})"

class Print:
    def __init__(self, value, line=0):
        self.line = line
        self.value = value
    def __repr__(self):
        return f"Print({self.value})"

class PrintD:
    def __init__(self, value, line=0):
        self.line = line
        self.value = value
    def __repr__(self):
        return f"PrintD({self.value})"

class Function:
    def __init__(self, name, params, body, return_type=None, line=0):
        self.line = line
        self.name = name
        self.params = params
        self.body = body
        self.return_type = return_type
    def __repr__(self):
        return f"Function('{self.name}', {self.params}, {self.body}, return_type={self.return_type})"

class Call:
    def __init__(self, name, args, line=0):
        self.line = line
        self.name = name
        self.args = args
    def __repr__(self):
        return f"Call('{self.name}', {self.args})"

class Return:
    def __init__(self, value, line=0):
        self.line = line
        self.value = value
    def __repr__(self):
        return f"Return({self.value})"

class IfElse:
    def __init__(self, condition, if_body, else_body, line=0):
        self.line = line
        self.condition = condition
        self.if_body = if_body
        self.else_body = else_body
    def __repr__(self):
        return f"IfElse({self.condition}, {self.if_body}, {self.else_body})"

class While:
    def __init__(self, condition, body, line=0):
        self.line = line
        self.condition = condition
        self.body = body
    def __repr__(self):
        return f"While({self.condition}, {self.body})"

class Break:
    def __init__(self, line=0):
        self.line = line
    def __repr__(self):
        return "Break()"

class Continue:
    def __init__(self, line=0):
        self.line = line
    def __repr__(self):
        return "Continue()"

class RawBlock:
    def __init__(self, body, exports=None, line=0):
        self.line = line
        self.body = body
        self.exports = exports or []
    def __repr__(self):
        return f"RawBlock({self.body}, {self.exports})"

class Export:
    def __init__(self, names, line=0):
        self.line = line
        self.names = names
    def __repr__(self):
        return f"Export({self.names})"

class Import:
    def __init__(self, module, items=None, alias=None, line=0):
        self.line = line
        self.module = module
        self.items = items or []
        self.alias = alias
    def __repr__(self):
        return f"Import('{self.module}', {self.items})"

class LoadLib:
    def __init__(self, lib_path, alias, line=0):
        self.line = line
        self.lib_path = lib_path
        self.alias = alias
    def __repr__(self):
        return f"LoadLib('{self.lib_path}', '{self.alias}')"

class Attribute:
    def __init__(self, obj, attr, line=0):
        self.line = line
        self.obj = obj
        self.attr = attr
    def __repr__(self):
        return f"Attribute({self.obj}, '{self.attr}')"

# ========== NEW POINTER NODES ==========

class Alloc:
    def __init__(self, size, line=0):
        self.line = line
        self.size = size
    def __repr__(self):
        return f"Alloc({self.size})"

class Free:
    def __init__(self, ptr, line=0):
        self.line = line
        self.ptr = ptr
    def __repr__(self):
        return f"Free({self.ptr})"

class PointerProperty:
    def __init__(self, ptr, property_name, line=0):
        self.line = line
        self.ptr = ptr
        self.property = property_name  # "value", "addr", "isValid", "isNull", "bytes"
    def __repr__(self):
        return f"PointerProperty({self.ptr}, '{self.property}')"

class PointerAssign:
    def __init__(self, ptr, property_name, value, line=0):
        self.line = line
        self.ptr = ptr
        self.property = property_name
        self.value = value
    def __repr__(self):
        return f"PointerAssign({self.ptr}, '{self.property}', {self.value})"

class PointerOffset:
    def __init__(self, ptr, offset, line=0):
        self.line = line
        self.ptr = ptr
        self.offset = offset
    def __repr__(self):
        return f"PointerOffset({self.ptr}, {self.offset})"

class ArrayIndex:
    def __init__(self, base, index, line=0):
        self.line = line
        self.base = base
        self.index = index
    def __repr__(self):
        return f"ArrayIndex({self.base}, {self.index})"

class ArrayIndexAssign:
    def __init__(self, base, index, value, line=0):
        self.line = line
        self.base = base
        self.index = index
        self.value = value
    def __repr__(self):
        return f"ArrayIndexAssign({self.base}, {self.index}, {self.value})"

class Slice:
    def __init__(self, base, start, end, line=0):
        self.line = line
        self.base = base
        self.start = start
        self.end = end
    def __repr__(self):
        return f"Slice({self.base}, {self.start}, {self.end})"

class Type:
    def __init__(self, name, line=0):
        self.line = line
        self.name = name
    def __repr__(self):
        return f"Type('{self.name}')"

class NovaError(Exception):
    def __init__(self, line=0):
        self.line = line
    pass

def runtime_error(msg):
    raise NovaError(f"[Nova Runtime Error] {msg}")

# ========== OOP AND BUILTIN NODES ==========

class Openf:
    def __init__(self, path, mode=None, line=1):
        self.path = path
        self.mode = mode
        self.line = line
    def __repr__(self):
        return f"Openf({self.path}, {self.mode})"

class ApiRequest:
    def __init__(self, url, method="GET", line=0):
        self.line = line
        self.url = url
        self.method = method
    def __repr__(self):
        return f"ApiRequest({self.url}, {self.method})"

class ApiGet:
    def __init__(self, request, line=0):
        self.line = line
        self.request = request
    def __repr__(self):
        return f"ApiGet({self.request})"

class ApiPost:
    def __init__(self, request, data, line=0):
        self.line = line
        self.request = request
        self.data = data
    def __repr__(self):
        return f"ApiPost({self.request}, {self.data})"

class ApiDownload:
    def __init__(self, request, filepath, line=0):
        self.line = line
        self.request = request
        self.filepath = filepath
    def __repr__(self):
        return f"ApiDownload({self.request}, {self.filepath})"

class OpenFile:
    def __init__(self, path, mode, line=0):
        self.line = line
        self.path = path
        self.mode = mode
    def __repr__(self):
        return f"OpenFile({self.path}, {self.mode})"

class ReadFile:
    def __init__(self, fd, line=0):
        self.line = line
        self.fd = fd
    def __repr__(self):
        return f"ReadFile({self.fd})"

class WriteFile:
    def __init__(self, fd, content, line=0):
        self.line = line
        self.fd = fd
        self.content = content
    def __repr__(self):
        return f"WriteFile({self.fd}, {self.content})"

class CloseFile:
    def __init__(self, fd, line=0):
        self.line = line
        self.fd = fd
    def __repr__(self):
        return f"CloseFile({self.fd})"

class SizeOf:
    def __init__(self, target, line=0):
        self.line = line
        self.target = target
    def __repr__(self):
        return f"SizeOf({self.target})"

class Len:
    def __init__(self, target, line=0):
        self.line = line
        self.target = target
    def __repr__(self):
        return f"Len({self.target})"

class StrConvert:
    def __init__(self, target, line=0):
        self.line = line
        self.target = target
    def __repr__(self):
        return f"StrConvert({self.target})"

class EnumDef:
    def __init__(self, name, variants, line=0):
        self.line = line
        self.name = name
        self.variants = variants
    def __repr__(self):
        return f"EnumDef('{self.name}', {self.variants})"

class ClassDef:
    def __init__(self, name, methods, fields, line=0):
        self.line = line
        self.name = name
        self.methods = methods
        self.fields = fields
    def __repr__(self):
        return f"ClassDef('{self.name}', {self.methods}, {self.fields})"

class NewInstance:
    def __init__(self, class_name, args, line=0):
        self.line = line
        self.class_name = class_name
        self.args = args
    def __repr__(self):
        return f"NewInstance('{self.class_name}', {self.args})"

class Self:
    def __init__(self, line=0):
        self.line = line
    def __repr__(self):
        return "Self()"

class MethodCall:
    def __init__(self, instance, method_name, args, line=0):
        self.line = line
        self.instance = instance
        self.method_name = method_name
        self.args = args
    def __repr__(self):
        return f"MethodCall({self.instance}, '{self.method_name}', {self.args})"

# ========== DATA STRUCTURE NODES ==========

class Data:
    def __init__(self, name, fields, line=0):
        self.line = line
        self.name = name
        self.fields = fields  # List of (name, type) tuples
    def __repr__(self):
        return f"Data('{self.name}', {self.fields})"

class DataField:
    def __init__(self, name, type_name, line=0):
        self.line = line
        self.name = name
        self.type_name = type_name
    def __repr__(self):
        return f"DataField('{self.name}', '{self.type_name}')"

class DataInstance:
    def __init__(self, data_name, line=0):
        self.line = line
        self.data_name = data_name
    def __repr__(self):
        return f"DataInstance('{self.data_name}')"

class DataFieldAccess:
    def __init__(self, instance, field_name, line=0):
        self.line = line
        self.instance = instance
        self.field_name = field_name
    def __repr__(self):
        return f"DataFieldAccess({self.instance}, '{self.field_name}')"

class DataFieldAssign:
    def __init__(self, instance, field_name, value, line=0):
        self.line = line
        self.instance = instance
        self.field_name = field_name
        self.value = value
    def __repr__(self):
        return f"DataFieldAssign({self.instance}, '{self.field_name}', {self.value})"

class ForLoop:
    def __init__(self, var_name, start, end, step, body, is_downto=False, line=0):
        self.var_name = var_name
        self.start = start
        self.end = end
        self.step = step
        self.body = body
        self.is_downto = is_downto
        self.line = line

    def __repr__(self):
        return f"ForLoop({self.var_name}, {self.start}, {self.end}, {self.step}, {self.is_downto}, {self.body})"

class ForIn:
    def __init__(self, var_name, collection, body, line=0):
        self.var_name = var_name
        self.collection = collection
        self.body = body
        self.line = line
        
    def __repr__(self):
        return f"ForIn({self.var_name}, {self.collection}, {self.body})"

class ListLiteral:
    def __init__(self, elements, line=0):
        self.line = line
        self.elements = elements
    def __repr__(self):
        return f"ListLiteral({self.elements})"

class DictLiteral:
    def __init__(self, keys, values, line=0):
        self.line = line
        self.keys = keys
        self.values = values
    def __repr__(self):
        return f"DictLiteral({self.keys}, {self.values})"

class Block:
    def __init__(self, stmts, line=0):
        self.line = line
        self.stmts = stmts
    def __repr__(self):
        return f"Block({self.stmts})"

class Try:
    def __init__(self, body, catch_var, catch_body, line=0):
        self.line = line
        self.body = body
        self.catch_var = catch_var
        self.catch_body = catch_body
    def __repr__(self):
        return f"Try({self.body}, {self.catch_var}, {self.catch_body})"

class Throw:
    def __init__(self, value, line=0):
        self.line = line
        self.value = value
    def __repr__(self):
        return f"Throw({self.value})"