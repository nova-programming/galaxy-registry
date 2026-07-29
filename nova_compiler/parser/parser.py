from nova_ast.nodes import *


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.in_raw = False
        self._comp_counter = 0

    def parse_type_annotation(self):
        token = self.current()
        if not token:
            return ""
            
        type_name = ""
        if token[0] in ("TYPE_INT", "TYPE_FLOAT", "TYPE_BOOL", "TYPE_STRING", "TYPE_BYTE", "TYPE_VOID"):
            type_name = self.eat(token[0])[1]
        elif token[0] == "IDENT":
            type_name = self.eat("IDENT")[1]
        else:
            return ""
            
        if self.current() and self.current()[0] == "LBRACKET":
            self.eat("LBRACKET")
            inner_type = self.parse_type_annotation()
            self.eat("RBRACKET")
            return f"{type_name}[{inner_type}]"
            
        return type_name

    def parse_data(self):
        """Parse data structure definition"""
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        self.eat("DATA")
        name = self.eat("IDENT")[1]
        
        self.eat("LBRACE")
        fields = []
        
        while self.current() and self.current()[0] != "RBRACE":
            self.skip_newlines()
            if self.current()[0] == "RBRACE":
                break
            
            field_name = self.eat("IDENT")[1]
            self.eat("COLON")
            
            # Handle type keywords
            type_token = self.current()
            if type_token[0] in ("TYPE_INT", "TYPE_FLOAT", "TYPE_BOOL", "TYPE_STRING"):
                type_name = self.eat(type_token[0])[1]
            else:
                type_name = self.eat("IDENT")[1]
            
            fields.append((field_name, type_name))
            
            # Optional semicolon or newline
            if self.current() and self.current()[0] in ("NEWLINE", "SEMICOLON"):
                self.eat(self.current()[0])
        
        self.eat("RBRACE")
        return Data(name, fields, line=line)

    def parse_data_instance(self, data_name):
        """Parse data instance creation: Point()"""
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        self.eat("LPAREN")
        self.eat("RPAREN")
        return DataInstance(data_name, line=line)

    def parse_for(self):
        """Parse for loop: for i = 0 to 10 { body } or for i in items { body }"""
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        self.eat("FOR")
        var_name = self.eat("IDENT")[1]
        
        if self.current() and self.current()[0] == "IN":
            self.eat("IN")
            collection = self.parse_expr()
            body = self.parse_block()
            from nova_ast.nodes import ForIn
            return ForIn(var_name, collection, body, line=line)
            
        self.eat("EQUALS")
        start = self.parse_expr()
        
        # Check direction
        is_downto = False
        if self.current() and self.current()[0] == "TO":
            self.eat("TO")
            is_downto = False
        elif self.current() and self.current()[0] == "DOWNTO":
            self.eat("DOWNTO")
            is_downto = True
        else:
            self._syntax_error("Expected 'to' or 'downto' in for loop")
        
        end = self.parse_expr()
        
        # Optional step
        step = None
        if self.current() and self.current()[0] == "STEP":
            self.eat("STEP")
            step = self.parse_expr()
        
        body = self.parse_block()
        
        # Default step is 1
        if step is None:
            step = Number(1, line=line)
        
        return ForLoop(var_name, start, end, step, body, is_downto, line=line)

    def current(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _line_col(self, token=None):
        if token is None:
            token = self.current()
        if not token:
            return ('?', 0)
        line = token[2] if len(token) > 2 else '?'
        col = (token[3] if len(token) > 3 else 0) if isinstance(line, int) else 0
        return (line, col)

    def _syntax_error(self, msg, token=None):
        """Raise SyntaxError with lineno/offset set for source context display."""
        if token is None:
            token = self.current()
        line, col = self._line_col(token)
        if not isinstance(line, int):
            # EOF fallback: use the last token's line if available
            if self.tokens:
                line = self.tokens[-1][2] if len(self.tokens[-1]) > 2 and isinstance(self.tokens[-1][2], int) else 1
                col = 0
            else:
                line = 1
                col = 0
        e = SyntaxError(msg)
        e.lineno = line
        e.offset = col + 1 if isinstance(col, int) else None
        raise e

    def eat(self, kind):
        token = self.current()
        if token and token[0] == kind:
            self.pos += 1
            return token
        line, col = self._line_col(token)
        got_kind = token[0] if token else 'EOF'
        got_val = token[1] if token else ''
        self._syntax_error(f"Expected {kind}, got {got_kind} ('{got_val}')", token)

    def skip_newlines(self):
        while self.current() and self.current()[0] == "NEWLINE":
            self.eat("NEWLINE")

    # ---------------- EXPRESSIONS ----------------

    def parse_expr(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        return self.parse_logic()

    def parse_logic(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        left = self.parse_compare()
        while self.current() and self.current()[0] in ("AND", "OR"):
            op = self.eat(self.current()[0])[1]
            right = self.parse_compare()
            # Desugar: a == b or c -> (a == b) or (a == c)
            if isinstance(left, Compare) and not isinstance(right, Compare) and not isinstance(right, BinOp):
                right_line = getattr(right, 'line', 0)
                right = Compare(left.left, left.op, right, line=right_line)
            left = BinOp(left, op, right, line=line)
        return left

    def parse_compare(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        left = self.parse_add()
        ops = {"GT", "LT", "GE", "LE", "EQEQ", "NOTEQ", "HAS"}
        while self.current() and self.current()[0] in ops:
            op = self.eat(self.current()[0])[1]
            right = self.parse_add()
            left = Compare(left, op, right, line=line)
        return left

    def parse_add(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        left = self.parse_mul()
        while self.current() and self.current()[0] in ("PLUS", "MINUS"):
            op = self.eat(self.current()[0])[1]
            right = self.parse_mul()
            if isinstance(left, Number) and isinstance(right, Number):
                if op == "+": left = Number(left.value + right.value, line=line)
                elif op == "-": left = Number(left.value - right.value, line=line)
                continue
            left = BinOp(left, op, right, line=line)
        return left

    def parse_mul(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        left = self.parse_unary()
        while self.current() and self.current()[0] in ("STAR", "SLASH", "PERCENT", "AMPERSAND", "GTGT", "LTLT", "PIPE", "CARET"):
            op = self.eat(self.current()[0])[1]
            right = self.parse_unary()
            if isinstance(left, Number) and isinstance(right, Number):
                if op == "*": left = Number(left.value * right.value, line=line)
                elif op == "/" and right.value != 0: left = Number(int(left.value / right.value), line=line)
                elif op == "%" and right.value != 0: left = Number(left.value % right.value, line=line)
                elif op == "&": left = Number(left.value & right.value, line=line)
                elif op == ">>": left = Number(left.value >> right.value, line=line)
                elif op == "<<": left = Number(left.value << right.value, line=line)
                elif op == "|": left = Number(left.value | right.value, line=line)
                elif op == "^": left = Number(left.value ^ right.value, line=line)
                continue
            left = BinOp(left, op, right, line=line)
        return left

    def parse_unary(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        if self.current() and self.current()[0] in ("MINUS", "NOT", "TILDE"):
            op = self.eat(self.current()[0])[1]
            return UnaryOp(op, self.parse_unary(), line=line)
        return self.parse_primary()

    def parse_primary(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        token = self.current()
        if not token:
            self._syntax_error("Unexpected end of file")
        kind = token[0]
        value = token[1]
        line = token[2] if len(token) > 2 else 0

        node = None

        if kind == "NUMBER":
            self.eat("NUMBER")
            node = Number(int(value, 0), line=line)
        elif kind == "FLOAT":
            self.eat("FLOAT")
            node = Number(float(value), line=line)
        
        elif kind == "STRING":
            self.eat("STRING")
            node = String(value[1:-1], line=line)
        
        elif kind == "TRUE":
            self.eat("TRUE")
            node = Boolean(True, line=line)
        
        elif kind == "FALSE":
            self.eat("FALSE")
            node = Boolean(False, line=line)
        
        elif kind == "LPAREN":
            self.eat("LPAREN")
            node = self.parse_expr()
            self.eat("RPAREN")

        elif kind == "SIZEOF":
            self.eat("SIZEOF")
            self.eat("LPAREN")
            target = self.parse_expr()
            self.eat("RPAREN")
            node = SizeOf(target, line=line)

        elif kind == "LEN":
            self.eat("LEN")
            self.eat("LPAREN")
            target = self.parse_expr()
            self.eat("RPAREN")
            node = Len(target, line=line)

        elif kind == "STR":
            self.eat("STR")
            self.eat("LPAREN")
            target = self.parse_expr()
            self.eat("RPAREN")
            node = StrConvert(target, line=line)

        elif kind == "OPENF":
            self.eat("OPENF")
            self.eat("LPAREN")
            path = self.parse_expr()
            mode = String("r", line=line)
            if self.current() and self.current()[0] == "COMMA":
                self.eat("COMMA")
                mode = self.parse_expr()
            self.eat("RPAREN")
            node = Openf(path, mode=mode, line=line)

        elif kind == "API":
            self.eat("API")
            self.eat("LPAREN")
            url = self.parse_expr()
            method = "GET"
            if self.current() and self.current()[0] == "COMMA":
                self.eat("COMMA")
                # For now just eat the method string and hardcode GET compilation later, 
                # or store it in ApiRequest node
                if self.current() and self.current()[0] == "STRING":
                    method = self.eat("STRING")[1][1:-1]
                else:
                    self.parse_expr() # fallback 
            self.eat("RPAREN")
            node = ApiRequest(url, method=method, line=line)

        elif kind == "OPEN":
            self.eat("OPEN")
            self.eat("LPAREN")
            path = self.parse_expr()
            self.eat("COMMA")
            mode = self.parse_expr()
            self.eat("RPAREN")
            node = OpenFile(path, mode, line=line)

        elif kind == "READ":
            self.eat("READ")
            self.eat("LPAREN")
            fd = self.parse_expr()
            self.eat("RPAREN")
            node = ReadFile(fd, line=line)

        elif kind == "SELF":
            self.eat("SELF")
            node = Self(line=line)
        
        elif kind == "ALLOC":
            node = self.parse_alloc()
        
        elif kind == "LBRACK":
            self.eat("LBRACK")
            elements = []
            if self.current() and self.current()[0] != "RBRACK":
                first_expr = self.parse_expr()
                # Check for list comprehension: [expr for x in list]
                if self.current() and self.current()[0] == "FOR":
                    return self._parse_list_comp(first_expr, line)
                elements.append(first_expr)
                while self.current() and self.current()[0] == "COMMA":
                    self.eat("COMMA")
                    if self.current() and self.current()[0] != "RBRACK":
                        elements.append(self.parse_expr())
            self.eat("RBRACK")
            node = ListLiteral(elements, line=line)

        elif kind == "LBRACE":
            self.eat("LBRACE")
            keys = []
            values = []
            if self.current() and self.current()[0] != "RBRACE":
                keys.append(self.parse_expr())
                self.eat("COLON")
                values.append(self.parse_expr())
                while self.current() and self.current()[0] == "COMMA":
                    self.eat("COMMA")
                    if self.current() and self.current()[0] != "RBRACE":
                        keys.append(self.parse_expr())
                        self.eat("COLON")
                        values.append(self.parse_expr())
            self.eat("RBRACE")
            node = DictLiteral(keys, values, line=line)

        elif kind == "IDENT":
            name = self.eat("IDENT")[1]
            
            # Check for function call / class instantiation / data instantiation
            if self.current() and self.current()[0] == "LPAREN":
                self.eat("LPAREN")
                args = []
                if self.current() and self.current()[0] != "RPAREN":
                    args.append(self.parse_expr())
                    while self.current() and self.current()[0] == "COMMA":
                        self.eat("COMMA")
                        if self.current() and self.current()[0] != "RPAREN":
                            args.append(self.parse_expr())
                self.eat("RPAREN")
                node = Call(name, args, line=line)
            else:
                node = Variable(name, line=line)
        elif kind == "COMMA":
            self.eat("COMMA")
            node = Variable(",", line=line)
        else:
            self._syntax_error(f"Unexpected token '{token[1]}' ({token[0]})")

        # Now, parse trailing suffix operators (. and [) in a loop
        while True:
            if not self.current():
                break
            
            next_kind = self.current()[0]
            if next_kind == "DOT":
                self.eat("DOT")
                # Allow keywords as method/property names (e.g. file1.write, file1.close)
                tok = self.current()
                if tok and tok[0] == "IDENT":
                    prop = self.eat("IDENT")[1]
                elif tok and tok[0] in ("WRITE", "CLOSE", "READ", "OPEN", "PRINT", "DATA",
                                        "IMPORT", "FREE", "ALLOC", "LEN", "STR", "SELF",
                                        "CLASS", "RETURN", "BREAK", "CONTINUE", "FOR",
                                        "WHILE", "IF", "ELSE", "ELIF", "IN", "TO",
                                        "STEP", "DOWNTO", "AND", "OR", "NOT", "HAS",
                                        "AS", "CONST", "DEF", "SIZEOF", "OPENF",
                                        "SWITCH", "CASE",
                                        "TYPE_INT", "TYPE_FLOAT", "TYPE_BOOL", "TYPE_STRING",
                                        "TRUE", "FALSE"):
                    prop = self.eat(tok[0])[1]
                else:
                    prop = self.eat("IDENT")[1]  # will raise proper error
                
                # Method call?
                if self.current() and self.current()[0] == "LPAREN":
                    self.eat("LPAREN")
                    args = []
                    if self.current() and self.current()[0] != "RPAREN":
                        args.append(self.parse_expr())
                        while self.current() and self.current()[0] == "COMMA":
                            self.eat("COMMA")
                            if self.current() and self.current()[0] != "RPAREN":
                                args.append(self.parse_expr())
                    self.eat("RPAREN")
                    node = MethodCall(node, prop, args, line=line)
                    continue
                
                # Pointer property vs Data field
                pointer_properties = ["value", "addr", "isValid", "isNull", "bytes", "value_byte", "value_word", "value_dword", "value_qword"]
                if prop in pointer_properties:
                    tok = self.current()
                    if tok and tok[0] in ("EQUALS", "PLUSEQ", "MINUSEQ", "STAREQ", "SLASHEQ", "PERCENTEQ"):
                        op = self.eat(tok[0])[1]
                        value = self.parse_expr()
                        if op != "=":
                            binop_op = op[:-1]
                            access_node = PointerProperty(node, prop, line=line)
                            value = BinOp(access_node, binop_op, value, line=line)
                        return PointerAssign(node, prop, value, line=line)
                    node = PointerProperty(node, prop, line=line)
                else:
                    tok = self.current()
                    if tok and tok[0] in ("EQUALS", "PLUSEQ", "MINUSEQ", "STAREQ", "SLASHEQ", "PERCENTEQ"):
                        op = self.eat(tok[0])[1]
                        value = self.parse_expr()
                        if op != "=":
                            binop_op = op[:-1]
                            access_node = DataFieldAccess(node, prop, line=line)
                            value = BinOp(access_node, binop_op, value, line=line)
                        return DataFieldAssign(node, prop, value, line=line)
                    node = DataFieldAccess(node, prop, line=line)
                continue
                
            elif next_kind == "LBRACK":
                self.eat("LBRACK")

                # Check for slice syntax [start:end] or [:end] or [start:]
                if self.current() and self.current()[0] == "COLON":
                    self.eat("COLON")
                    end_expr = self.parse_expr() if self.current() and self.current()[0] != "RBRACK" else None
                    self.eat("RBRACK")
                    node = Slice(node, None, end_expr, line=line)
                    continue

                index = self.parse_expr()
                if self.current() and self.current()[0] == "COLON":
                    self.eat("COLON")
                    end_expr = self.parse_expr() if self.current() and self.current()[0] != "RBRACK" else None
                    self.eat("RBRACK")
                    node = Slice(node, index, end_expr, line=line)
                    continue

                self.eat("RBRACK")
                tok = self.current()
                if tok and tok[0] in ("EQUALS", "PLUSEQ", "MINUSEQ", "STAREQ", "SLASHEQ", "PERCENTEQ"):
                    op = self.eat(tok[0])[1]
                    value = self.parse_expr()
                    if op != "=":
                        binop_op = op[:-1]
                        access_node = ArrayIndex(node, index, line=line)
                        value = BinOp(access_node, binop_op, value, line=line)
                    return ArrayIndexAssign(node, index, value, line=line)
                node = ArrayIndex(node, index, line=line)
                continue
                
            else:
                break
                
        return node

    def parse_alloc(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        self.eat("ALLOC")
        if not self.current() or self.current()[0] != "LPAREN":
            self._syntax_error("Expected '(' after alloc")
        self.eat("LPAREN")
        size = self.parse_expr()
        self.eat("RPAREN")
        return Alloc(size, line=line)

    # ---------------- STATEMENTS ----------------

    def parse_enum(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        self.eat("ENUM")
        name = self.eat("IDENT")[1]
        self.eat("LBRACE")
        variants = []
        while self.current() and self.current()[0] == "IDENT":
            variants.append(self.eat("IDENT")[1])
            if self.current() and self.current()[0] == "COMMA":
                self.eat("COMMA")
        self.eat("RBRACE")
        return EnumDef(name, variants, line=line)

    def parse_class(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        self.eat("CLASS")
        name = self.eat("IDENT")[1]
        self.eat("LBRACE")
        methods = []
        fields = []
        while self.current() and self.current()[0] != "RBRACE":
            self.skip_newlines()
            if self.current()[0] == "RBRACE":
                break

            # Simple field vs method parsing
            if self.current()[0] == "DEF":
                methods.append(self.parse_function())
            else:
                field_name = self.eat("IDENT")[1]
                field_type = ""
                if self.current() and self.current()[0] == "COLON":
                    self.eat("COLON")
                    field_type = self.parse_type_annotation()

                # Default assignments in class body not yet supported, just taking names
                if self.current() and self.current()[0] == "EQUALS":
                    self.eat("EQUALS")
                    self.parse_expr() # Skip initial values for now
                fields.append((field_name, field_type))
            self.skip_newlines()

        self.eat("RBRACE")
        return ClassDef(name, methods, fields, line=line)

    def parse_statement(self):
        self.skip_newlines()
        token = self.current()
        if not token:
            return None
        kind = token[0]
        line = token[2] if len(token) > 2 else 0

        if kind == "ENUM":
            return self.parse_enum()
        if kind == "CLASS":
            return self.parse_class()
        if kind == "IMPORT":
            return self.parse_import()
        if kind == "RAW":
            return self.parse_raw()
        if kind == "FOR":
            return self.parse_for()
        if kind == "DEF":
            return self.parse_function()
        if kind == "PRINTD":
            self.eat("PRINTD")
            self.eat("LPAREN")
            value = self.parse_expr()
            self.eat("RPAREN")
            return PrintD(value, line=line)
        if kind == "PRINT":
            self.eat("PRINT")
            self.eat("LPAREN")
            value = self.parse_expr()
            self.eat("RPAREN")
            return Print(value, line=line)
        if kind == "WRITE":
            self.eat("WRITE")
            self.eat("LPAREN")
            fd = self.parse_expr()
            self.eat("COMMA")
            content = self.parse_expr()
            self.eat("RPAREN")
            return WriteFile(fd, content, line=line)
        if kind == "CLOSE":
            self.eat("CLOSE")
            self.eat("LPAREN")
            fd = self.parse_expr()
            self.eat("RPAREN")
            return CloseFile(fd, line=line)
        if kind == "IF":
            return self.parse_if()
        if kind == "SWITCH":
            return self.parse_switch()
        if kind == "WHILE":
            return self.parse_while()
        if kind == "RETURN":
            self.eat("RETURN")
            if self.current() and self.current()[0] in ('RBRACE', 'NEWLINE', 'EOF'):
                return Return(Number(0), line=line)
            return Return(self.parse_expr(), line=line)
        if kind == "BREAK":
            self.eat("BREAK")
            return Break(line=line)
        if kind == "CONTINUE":
            self.eat("CONTINUE")
            return Continue(line=line)
        if kind == "FREE":
            return self.parse_free()
        if kind == "DATA":
            return self.parse_data()
        if kind == "TRY":
            return self.parse_try()
        if kind == "THROW":
            self.eat("THROW")
            value = self.parse_expr()
            return Throw(value, line=line)

        is_const = False
        type_name = None
        if kind == "CONST":
            self.eat("CONST")
            is_const = True
            token = self.current()
            kind = token[0]

        expr = self.parse_expr()

        if isinstance(expr, Variable) and self.current() and self.current()[0] == "COLON":
            self.eat("COLON")
            type_name = self.parse_type_annotation()
            expr.type_name = type_name

        tok = self.current()
        if tok and tok[0] in ("EQUALS", "PLUSEQ", "MINUSEQ", "STAREQ", "SLASHEQ", "PERCENTEQ"):
            op = self.eat(tok[0])[1]
            value = self.parse_expr()
            if isinstance(expr, Variable):
                if op != "=":
                    binop_op = op[:-1]
                    value = BinOp(expr, binop_op, value, line=line)
                return Assignment(expr.name, value, type_name=expr.type_name, is_const=is_const, line=line)
        return expr

    def parse_free(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        self.eat("FREE")
        if not self.current() or self.current()[0] != "LPAREN":
            self._syntax_error("Expected '(' after free")
        self.eat("LPAREN")
        ptr = self.parse_expr()
        self.eat("RPAREN")
        return Free(ptr, line=line)

    def parse_try(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        self.eat("TRY")
        body = self.parse_block()
        self.eat("CATCH")
        catch_var = self.eat("IDENT")[1]
        catch_body = self.parse_block()
        return Try(body, catch_var, catch_body, line=line)

    def parse_function(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        self.eat("DEF")
        name = self.eat("IDENT")[1]
        self.eat("LPAREN")
        params = []
        if self.current() and self.current()[0] != "RPAREN":
            param_name = self.eat("IDENT")[1]
            param_type = ""
            if self.current() and self.current()[0] == "COLON":
                self.eat("COLON")
                param_type = self.parse_type_annotation()
            params.append((param_name, param_type))

            while self.current() and self.current()[0] == "COMMA":
                self.eat("COMMA")
                param_name = self.eat("IDENT")[1]
                param_type = ""
                if self.current() and self.current()[0] == "COLON":
                    self.eat("COLON")
                    param_type = self.parse_type_annotation()
                params.append((param_name, param_type))
        self.eat("RPAREN")

        return_type = ""
        if self.current() and self.current()[0] == "ARROW":
            self.eat("ARROW")
            return_type = self.parse_type_annotation()

        self.eat("LBRACE")
        body = []
        while self.current() and self.current()[0] != "RBRACE":
            self.skip_newlines()
            if self.current()[0] == "RBRACE":
                break
            stmt = self.parse_statement()
            if stmt:
                body.append(stmt)
            self.skip_newlines()
        self.eat("RBRACE")
        return Function(name, params, body, return_type=return_type, line=line)

    def parse_block(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        self.eat("LBRACE")
        body = []
        while self.current() and self.current()[0] != "RBRACE":
            self.skip_newlines()
            if self.current()[0] == "RBRACE":
                break
            stmt = self.parse_statement()
            if stmt:
                body.append(stmt)
            self.skip_newlines()
            if self.current() and self.current()[0] == "SEMICOLON":
                self.eat("SEMICOLON")
        self.eat("RBRACE")
        return body

    def parse_import(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        self.eat("IMPORT")

        # Check if it's an FFI string import `import "c" as libc`
        if self.current() and self.current()[0] == "STRING":
            lib_path = self.eat("STRING")[1][1:-1] # Remove quotes
            self.eat("AS")
            alias = self.eat("IDENT")[1]
            return LoadLib(lib_path, alias, line=line)

        # Standard .nv module import `import math` or `import math as m`
        module_name = self.eat("IDENT")[1]
        alias = None
        if self.current() and self.current()[0] == "AS":
            self.eat("AS")
            alias = self.eat("IDENT")[1]
        return Import(module_name, alias=alias, line=line)

    def parse_raw(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        self.eat("RAW")
        self.eat("LBRACE")
        self.in_raw = True
        body = []
        exports = []
        while self.current() and self.current()[0] != "RBRACE":
            self.skip_newlines()
            if self.current()[0] == "RBRACE":
                break
            if self.current()[0] == "EXPORT":
                exp = self.parse_export()
                exports.extend(exp.names)
            else:
                stmt = self.parse_statement()
                if stmt:
                    body.append(stmt)
            self.skip_newlines()
        self.eat("RBRACE")
        self.in_raw = False
        return RawBlock(body, exports, line=line)

    def parse_export(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        self.eat("EXPORT")
        self.eat("LBRACE")
        items = []
        while self.current() and self.current()[0] != "RBRACE":
            items.append(self.eat("IDENT")[1])
            if self.current() and self.current()[0] == "COMMA":
                self.eat("COMMA")
        self.eat("RBRACE")
        return Export(items, line=line)

    def parse_if(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        self.eat("IF")
        cond = self.parse_expr()
        then = self.parse_block()
        else_body = self._parse_if_tail()
        return IfElse(cond, then, else_body, line=line)

    def _parse_if_tail(self):
        """Parse the optional else/elif tail of an if statement."""
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        if not self.current():
            return []
        if self.current()[0] == "ELIF":
            self.eat("ELIF")
            elif_cond = self.parse_expr()
            elif_body = self.parse_block()
            tail = self._parse_if_tail()
            return [IfElse(elif_cond, elif_body, tail, line=line)]
        if self.current()[0] == "ELSE":
            self.eat("ELSE")
            return self.parse_block()
        return []

    def parse_switch(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        self.eat("SWITCH")
        expr = self.parse_expr()
        self.eat("LBRACE")
        cases = []
        else_body = []
        while self.current() and self.current()[0] not in ("RBRACE", "EOF"):
            if self.current()[0] == "CASE":
                self.eat("CASE")
                case_expr = self.parse_expr()
                case_body = self.parse_block()
                cases.append((case_expr, case_body))
            elif self.current()[0] == "ELSE":
                self.eat("ELSE")
                else_body = self.parse_block()
            else:
                break
        self.eat("RBRACE")
        # Desugar: build if-elif-else chain from last case to first
        current_else = else_body
        for case_expr, case_body in reversed(cases):
            cond = Compare(expr, "==", case_expr, line=line)
            current_else = [IfElse(cond, case_body, current_else, line=line)]
        if not cases:
            return else_body[0] if else_body else None
        # current_else is [IfElse(...)] — return the node
        return current_else[0]

    def parse_while(self):
        line = self.current()[2] if self.current() and len(self.current()) > 2 else 0
        self.eat("WHILE")
        cond = self.parse_expr()
        body = self.parse_block()
        return While(cond, body, line=line)

    def _parse_list_comp(self, expr, line):
        """Parse list comprehension: [expr for x in list] or [expr for x in list if cond]"""
        self.eat("FOR")
        target = self.eat("IDENT")[1]
        self.eat("IN")
        iterable = self.parse_expr()

        filter_expr = None
        if self.current() and self.current()[0] == "IF":
            self.eat("IF")
            filter_expr = self.parse_expr()

        self.eat("RBRACK")

        c = self._comp_counter
        self._comp_counter += 1
        result_var = f"__comp_{c}"
        iter_var = f"__iter_{c}"
        index_var = f"__i_{c}"

        body_stmts = [Assignment(target, ArrayIndex(Variable(iter_var, line=line), Variable(index_var, line=line), line=line), line=line)]

        append_call = MethodCall(Variable(result_var, line=line), "append", [expr], line=line)

        if filter_expr:
            body_stmts.append(IfElse(filter_expr, [append_call], [], line=line))
        else:
            body_stmts.append(append_call)

        for_loop = ForLoop(
            index_var,
            Number(0, line=line),
            BinOp(Len(Variable(iter_var, line=line), line=line), "-", Number(1, line=line), line=line),
            Number(1, line=line),
            body_stmts,
            False,
            line=line
        )

        return Block([
            Assignment(result_var, ListLiteral([], line=line), line=line),
            Assignment(iter_var, iterable, line=line),
            for_loop,
            Variable(result_var, line=line)
        ], line=line)

    def parse(self):
        program = []
        while self.current():
            self.skip_newlines()
            if not self.current():
                break
            stmt = self.parse_statement()
            if stmt:
                program.append(stmt)
        # Desugar enums into const assignments
        return _desugar_enums(program)


def _desugar_enums(program):
    """Convert EnumDef nodes into const integer assignments."""
    result = []
    for node in program:
        if isinstance(node, EnumDef):
            for i, variant in enumerate(node.variants):
                const_name = f"{node.name}_{variant}"
                result.append(Assignment(
                    Variable(const_name, type_name="int", line=node.line),
                    Number(i, line=node.line),
                    is_const=True,
                    line=node.line
                ))
        else:
            result.append(node)
    return result
