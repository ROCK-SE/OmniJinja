"""
OmniJinja Dependency Analysis Utility
------------------------------------
This module provides utilities to statically analyze Python source code to 
determine if it depends on Flask or Jinja2. This is used by the extension 
orchestrator to decide whether a file should be parsed for template metadata.
"""
import ast

TEMPLATE_RELATED_IMPORTS = ('flask', 'jinja2')

def _has_template_related_import_text(source_code: str) -> bool:
    for line in source_code.splitlines():
        stripped = line.strip()
        if stripped.startswith(('import flask', 'import jinja2', 'from flask', 'from jinja2')):
            return True
    return False

def _is_string_literal(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)

def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ''

def _looks_like_static_template_render(node: ast.Call) -> bool:
    name = _call_name(node.func)
    if name not in {'render_template', 'render'}:
        return False

    if any(_is_string_literal(arg) for arg in node.args[:2]):
        return True

    return any(
        kw.arg in {'template', 'template_name', 'name'}
        and _is_string_literal(kw.value)
        for kw in node.keywords
    )

def has_flask_or_jinja_import(source_code: str) -> bool:

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return _has_template_related_import_text(source_code)

    for node in ast.walk(tree):
        
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level_pkg = alias.name.split('.')[0]
                if top_level_pkg in TEMPLATE_RELATED_IMPORTS:
                    return True
                    
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top_level_pkg = node.module.split('.')[0]
                if top_level_pkg in TEMPLATE_RELATED_IMPORTS:
                    return True

        elif isinstance(node, ast.Call) and _looks_like_static_template_render(node):
            return True

    return False

