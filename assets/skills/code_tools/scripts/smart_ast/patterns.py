"""smart_ast_search/patterns.py"""

# Language-specific semantic shorthands
LANG_PATTERNS = {
    "python": {
        "classes": "class $NAME",
        "class": "class $NAME",
        "functions": "def $NAME($$$)",
        "function": "def $NAME($$$)",
        "methods": "def $NAME($$$)",
        "method": "def $NAME($$$)",
        "decorators": "@$DECORATOR\ndef $NAME($$$)",
        "decorator": "@$DECORATOR\ndef $NAME($$$)",
    },
    "rust": {
        "structs": "struct $NAME",
        "struct": "struct $NAME",
        "enums": "enum $NAME",
        "enum": "enum $NAME",
        "functions": "fn $NAME($$$)",
        "function": "fn $NAME($$$)",
        "impls": "impl $NAME { $$$ }",
        "impl": "impl $NAME { $$$ }",
        "traits": "trait $NAME { $$$ }",
        "trait": "trait $NAME { $$$ }",
    },
    "javascript": {
        "classes": "class $NAME",
        "class": "class $NAME",
        "functions": "function $NAME($$$)",
        "function": "function $NAME($$$)",
        "arrows": "($$$) => $$$",
        "arrow": "($$$) => $$$",
    },
    "typescript": {
        "interfaces": "interface $NAME { $$$ }",
        "interface": "interface $NAME { $$$ }",
        "classes": "class $NAME",
        "class": "class $NAME",
        "types": "type $NAME = $$$",
        "type": "type $NAME = $$$",
        "functions": "function $NAME($$$)",
        "function": "function $NAME($$$)",
    },
}

# Compatibility mapping (legacy)
COMMON_PATTERNS = LANG_PATTERNS["python"]
