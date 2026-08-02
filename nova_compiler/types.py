class Type:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        if not isinstance(other, Type): return False
        if isinstance(self, AnyType) or isinstance(other, AnyType): return True
        return self.name == other.name

    def __str__(self):
        return self.name

class ScalarType(Type):
    pass

class StructType(Type):
    def __init__(self, name, fields=None):
        super().__init__(name)
        self.fields = fields or {}  # dict[str, Type]

class FuncType(Type):
    def __init__(self, params, ret):
        super().__init__("func")
        self.params = params  # list[Type]
        self.ret = ret        # Type

    def __eq__(self, other):
        if isinstance(other, AnyType): return True
        if not isinstance(other, FuncType): return False
        if len(self.params) != len(other.params): return False
        for a, b in zip(self.params, other.params):
            if a != b: return False
        return self.ret == other.ret

    def __str__(self):
        params_str = ", ".join(str(p) for p in self.params)
        return f"func({params_str}) -> {self.ret}"

class GenericType(Type):
    def __init__(self, name):
        super().__init__(name)

class ListType(Type):
    def __init__(self, element_type):
        super().__init__("list")
        self.element_type = element_type

    def __eq__(self, other):
        if isinstance(other, AnyType): return True
        if not isinstance(other, ListType): return False
        return self.element_type == other.element_type

    def __str__(self):
        return f"list[{self.element_type}]"

class DictType(Type):
    def __init__(self, value_type=None):
        super().__init__("dict")
        self.value_type = value_type or AnyType()

    def __eq__(self, other):
        if isinstance(other, AnyType): return True
        if not isinstance(other, DictType): return False
        return True

class AnyType(Type):
    def __init__(self):
        super().__init__("any")

class DynType(Type):
    def __init__(self):
        super().__init__("dyn")

# Built-in scalar types
IntType = ScalarType("int")
FloatType = ScalarType("float")
BoolType = ScalarType("bool")
StringType = ScalarType("string")
ByteType = ScalarType("byte")
VoidType = ScalarType("void")
FileType = ScalarType("file")

def resolve_type_annotation(annotation_str):
    """Convert a string annotation like 'int' into a Type object."""
    if not annotation_str:
        return AnyType()
    
    # Handle list[...]
    if annotation_str.startswith("list[") and annotation_str.endswith("]"):
        inner = annotation_str[5:-1]
        return ListType(resolve_type_annotation(inner))
    if annotation_str == "list":
        return ListType(AnyType())
        
    mapping = {
        "int": IntType,
        "float": FloatType,
        "bool": BoolType,
        "string": StringType,
        "byte": ByteType,
        "void": VoidType,
        "file": FileType,
        "any": AnyType(),
        "dyn": DynType(),
    }
    
    if annotation_str in mapping:
        return mapping[annotation_str]
        
    # Assume it's a struct type if not built-in (will be resolved fully in inference)
    return StructType(annotation_str)
