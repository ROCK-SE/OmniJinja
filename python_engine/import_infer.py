"""
OmniJinja Dependency Analysis Utility
------------------------------------
This module provides utilities to statically analyze Python source code to 
determine if it depends on Flask or Jinja2. This is used by the extension 
orchestrator to decide whether a file should be parsed for template metadata.
"""
import ast

def has_flask_or_jinja_import(source_code: str) -> bool:

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level_pkg = alias.name.split('.')[0]
                if top_level_pkg in ('flask', 'jinja2'):
                    return True
                    
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top_level_pkg = node.module.split('.')[0]
                if top_level_pkg in ('flask', 'jinja2'):
                    return True

    return False

