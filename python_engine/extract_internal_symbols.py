"""
OmniJinja Internal Symbol Extractor
----------------------------------
Extracts local variable definitions (e.g., from {% set %} and {% for %}) within 
Jinja2 templates. It resolves types by bridging the gap between template 
logic and backend Python schemas.
"""
import json
import re
from jinja2 import Environment, nodes
from jinja2.visitor import NodeVisitor

class JinjaSymbolExtractor(NodeVisitor):
    def __init__(self, backend_schema: dict):
        self.backend_schema = backend_schema or {}
        self.scope_stack = [{}]  # Use scope stack instead of flat dict
        
        self.LOOP_PROPERTIES = {
            "index": {"__type__": "Integer"}, "index0": {"__type__": "Integer"},
            "revindex": {"__type__": "Integer"}, "revindex0": {"__type__": "Integer"},
            "first": {"__type__": "Boolean"}, "last": {"__type__": "Boolean"},
            "length": {"__type__": "Integer"}, "depth": {"__type__": "Integer"},
            "depth0": {"__type__": "Integer"}
        }

    def _extract_path(self, node) -> list:
        """Recursively converts an AST node path (e.g., user.id) into a list of strings."""
        if isinstance(node, nodes.Name): return [node.name]
        elif isinstance(node, nodes.Getattr):
            base = self._extract_path(node.node)
            return base + [node.attr] if base else []
        return []

    def _resolve_schema(self, path: list, is_iterable=False) -> dict:
        """
        Traces a variable path through current scopes to find its type schema.
        
        Args:
            path: The attribute path (e.g., ['u', 'profile']).
            is_iterable: If True, resolves the type of the elements inside the collection.
        """
        if not path: return {}
        
        # Search for the base variable from innermost scope to outermost
        current = None
        for scope in reversed(self.scope_stack):
            if path[0] in scope:
                current = scope[path[0]]
                break
      
        if current is None:
            current = self.backend_schema.get(path[0])
            
        if current is None: return {}

        for part in path[1:]:
            if isinstance(current, dict) and part in current: current = current[part]
            else: return {}

        if is_iterable:
            if isinstance(current, list) and len(current) > 0: return current[0] 
            elif isinstance(current, dict) and current.get("__is_iterable__"):
                return current.get("__element__", {})
            return {}
            
        return current if isinstance(current, dict) else {"__type__": type(current).__name__.capitalize()}

    def visit_Assign(self, node: nodes.Assign):
        self.visit(node.node)
        if isinstance(node.target, nodes.Name):
            if isinstance(node.node, nodes.Const):
                self.scope_stack[-1][node.target.name] = {"__type__": type(node.node.value).__name__.capitalize()}
            else:
                path = self._extract_path(node.node)
                self.scope_stack[-1][node.target.name] = self._resolve_schema(path)

    
    # {% for item in avatars %}
    #     {{item.age}}
    # {% endfor %} 
    # Evaluates the iterable object to determine the true data type of its elements 
    #        (e.g., extracting the 'Order' schema from a list of 'orders').
    def visit_For(self, node: nodes.For):
        self.visit(node.iter)
        iter_path = self._extract_path(node.iter)
        iter_type_data = self._resolve_schema(iter_path, is_iterable=True)

        # Create a new local scope for the loop with the loop variable and 'loop' object
        local_scope = {"loop": self.LOOP_PROPERTIES}
        if isinstance(node.target, nodes.Name):
            local_scope[node.target.name] = iter_type_data if iter_type_data else {"__type__": "Any"}
            
        self.scope_stack.append(local_scope)
        for child in node.body: 
            self.visit(child)
        self.scope_stack.pop()

    def _regex_fallback(self, template_code: str):
        """
        Regex-based recovery for incomplete or invalid ASTs.
        Ensures variables are still detected while the user is typing (e.g., unclosed tags).
        """
        
        set_pattern = re.compile(r'\{%\s*set\s+([a-zA-Z0-9_]+)\s*=\s*([a-zA-Z0-9_.]+)')
        for match in set_pattern.finditer(template_code):
            var_name, path_str = match.groups()
            self.scope_stack[-1][var_name] = self._resolve_schema(path_str.split('.'))
            
        for_pattern = re.compile(r'\{%\s*for\s+([a-zA-Z0-9_]+)\s+in\s+([a-zA-Z0-9_.]+)')
        for match in for_pattern.finditer(template_code):
            var_name, path_str = match.groups()
            iter_data = self._resolve_schema(path_str.split('.'), is_iterable=True)
            # Note: For loop variables in regex fallback are added to current scope
            # They would be properly scoped in the AST visitor
            self.scope_stack[-1][var_name] = iter_data if iter_data else {"__type__": "Any"}
            self.scope_stack[-1]["loop"] = self.LOOP_PROPERTIES

    def extract(self, template_code: str) -> dict:
        try:
            ast_tree = Environment().parse(template_code)
            self.visit(ast_tree)
        except Exception:
            
            self._regex_fallback(template_code)
            
        # Return only the global scope (scope_stack[0]) which contains variables 
        # valid outside of any loops or macros
        return self.scope_stack[0]
