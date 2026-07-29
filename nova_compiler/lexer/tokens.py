"""Token definitions for the Nova lexer"""

import re

TOKEN_SPEC = [
    # Literals (FLOAT must come before NUMBER so 3.14 isn't split)
    ("HEX",      r"0[xX][0-9a-fA-F]+"),
    ("BIN",      r"0[bB][01]+"),
    ("FLOAT",    r"\d+\.\d+"),
    ("NUMBER",   r"\d+"),
    ("STRING",   r'"(?:[^"\\]|\\.)*"'),
    ("TRUE",     r"true\b"),
    ("FALSE",    r"false\b"),
    ("NULL",     r"null\b"),

    # Keywords
    ("CLASS",    r"class\b"),
    ("PRINTD",   r"printd\b"),
    ("PRINT",    r"print\b"),
    ("DEF",      r"def\b"),
    ("DATA",     r"data\b"),
    ("SELF",     r"self\b"),
    ("SIZEOF",   r"sizeof\b"),
    ("OPENF",    r"openf\b"),
    ("API",      r"api\b"),
    ("LEN",      r"len\b"),
    ("OPEN",     r"open\b"),
    ("READ",     r"read\b"),
    ("WRITE",    r"write\b"),
    ("CLOSE",    r"close\b"),
    ("RETURN",   r"return\b"),
    ("IF",       r"if\b"),
    ("ELSE",     r"else\b"),
    ("WHILE",    r"while\b"),
    ("FOR",      r"for\b"),
    ("IN",       r"in\b"),
    ("TO",       r"to\b"),
    ("DOWNTO",   r"downto\b"),
    ("STEP",     r"step\b"),
    ("AND",      r"and\b"),
    ("OR",       r"or\b"),
    ("NOT",      r"not\b"),
    ("BREAK",    r"break\b"),
    ("CONTINUE", r"continue\b"),
    ("FROM",     r"from\b"),
    ("IMPORT",   r"import\b"),
    ("AS",       r"as\b"),
    ("ALLOC",    r"alloc\b"),
    ("FREE",     r"free\b"),
    ("HAS",      r"has\b"),
    ("ELIF",     r"elif\b"),
    ("SWITCH",   r"switch\b"),
    ("CASE",     r"case\b"),
    ("TRY",      r"try\b"),
    ("CATCH",    r"catch\b"),
    ("THROW",    r"throw\b"),

    # Directives
    ("RAW",      r"@raw"),
    ("EXPORT",   r"@export"),

    # Type keywords
    ("TYPE_INT",    r"int\b"),
    ("TYPE_FLOAT",  r"float\b"),
    ("TYPE_BOOL",   r"bool\b"),
    ("TYPE_STRING", r"string\b"),
    ("CONST",       r"const\b"),
    ("ENUM",        r"enum\b"),
    ("STR",         r"str\b"),

    # Identifiers
    ("IDENT",    r"[a-zA-Z_@][a-zA-Z0-9_@]*"),

    # Comparison Operators
    ("EQEQ",     r"=="),
    ("NOTEQ",    r"!="),
    ("GE",       r">="),
    ("LE",       r"<="),
    ("GTGT",     r">>"),
    ("LTLT",     r"<<"),
    ("GT",       r">"),
    ("LT",       r"<"),

    # Arithmetic & Assignment Operators
    ("PLUSEQ",   r"\+="),
    ("MINUSEQ",  r"-="),
    ("STAREQ",   r"\*="),
    ("SLASHEQ",  r"/="),
    ("PERCENTEQ", r"%="),
    ("PLUS",     r"\+"),
    ("ARROW",    r"->"),
    ("MINUS",    r"-"),
    ("STAR",     r"\*"),
    ("SLASH",    r"/"),
    ("PERCENT",  r"%"),
    ("AMPERSAND", r"&"),
    ("PIPE",     r"\|"),
    ("CARET",    r"\^"),
    ("TILDE",    r"~"),
    ("EQUALS",   r"="),

    # Delimiters
    ("LPAREN",   r"\("),
    ("RPAREN",   r"\)"),
    ("LBRACE",   r"\{"),
    ("RBRACE",   r"\}"),
    ("LBRACK",   r"\["),
    ("RBRACK",   r"\]"),
    ("COMMA",    r","),
    ("DOT",      r"\."),
    ("COLON",    r":"),
    ("SEMICOLON", r";"),

    # Formatting & Metadata
    ("NEWLINE",  r"\n"),
    ("COMMENT",  r"\#.*"),
    ("SKIP",     r"[ \t\r]+"),
    ("MISMATCH", r"."),
]

TOKEN_REGEX = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC))