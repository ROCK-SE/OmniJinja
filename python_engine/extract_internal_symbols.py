"""
OmniJinja Internal Symbol Extractor
----------------------------------
Extracts local variable definitions (e.g., from {% set %} and {% for %}) within 
Jinja2 templates. It resolves types by bridging the gap between template 
logic and backend Python schemas.
"""

import re
from jinja2 import Environment, nodes
from jinja2.visitor import NodeVisitor

class JinjaSymbolExtractor(NodeVisitor):
    def __init__(self, backend_schema: dict):
        self.backend_schema = backend_schema or {}
        
        # Store both global variables and spatial scoped variables
        self.extracted_data = {
            "globals": {},  
            "scoped": []    
        }
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

    def _get_block_end_line(self, node: nodes.Node) -> int:
        """Approximates the end line of an AST block by finding the maximum line number among its children."""
        max_line = node.lineno
        for child in node.find_all(nodes.Node):
            if hasattr(child, 'lineno') and child.lineno > max_line:
                max_line = child.lineno
        return max_line + 1

    def visit_Assign(self, node: nodes.Assign):
        self.visit(node.node)
        if isinstance(node.target, nodes.Name):
            if isinstance(node.node, nodes.Const):
                schema = {"__type__": type(node.node.value).__name__.capitalize()}
            else:
                path = self._extract_path(node.node)
                schema = self._resolve_schema(path)
            
            schema["def_line"] = node.lineno 
            
            self.extracted_data["globals"][node.target.name] = schema
            self.scope_stack[0][node.target.name] = schema

    # {% for item in avatars %}
    #     {{item.age}}
    # {% endfor %} 
    # Evaluates the iterable object to determine the true data type of its elements 
    # (e.g., extracting the 'Order' schema from a list of 'orders').
    
    def visit_For(self, node: nodes.For):
        self.visit(node.iter)
        iter_path = self._extract_path(node.iter)
        iter_type_data = self._resolve_schema(iter_path, is_iterable=True)

        # Create a new local scope for the loop with the loop variable and 'loop' object
        local_scope = {"loop": self.LOOP_PROPERTIES}
        if isinstance(node.target, nodes.Name):
            local_scope[node.target.name] = iter_type_data if iter_type_data else {"__type__": "Any"}
            
        # Calculate spatial scope range (start and end line)
        start_line = node.lineno
        end_line = self._get_block_end_line(node)
        
        # Save spatial scope data
        self.extracted_data["scoped"].append({
            "type": "for",
            "scope_range": {"start_line": start_line, "end_line": end_line},
            "vars": local_scope
        })
            
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
            schema = self._resolve_schema(path_str.split('.'))
            
            start_line = template_code[:match.start()].count('\n') + 1
            schema["def_line"] = start_line
            
            self.extracted_data["globals"][var_name] = schema
            self.scope_stack[0][var_name] = schema
            
        for_pattern = re.compile(r'\{%\s*for\s+([a-zA-Z0-9_]+)\s+in\s+([a-zA-Z0-9_.]+)')
        for match in for_pattern.finditer(template_code):
            var_name, path_str = match.groups()
            iter_data = self._resolve_schema(path_str.split('.'), is_iterable=True)
            
            # Calculate approx start line for fallback
            start_line = template_code[:match.start()].count('\n') + 1
            
            scoped_vars = {
                var_name: iter_data if iter_data else {"__type__": "Any"},
                "loop": self.LOOP_PROPERTIES
            }
            
            # # Without closing tag, assume scope ends at EOF (999999)
            # self.extracted_data["scoped"].append({
            #     "type": "for_fallback",
            #     "scope_range": {"start_line": start_line, "end_line": 999999},
            #     "vars": scoped_vars
            # })
            
            text_after_for = template_code[match.end():]
            endfor_match = re.search(r'\{%\s*endfor\s*%\}', text_after_for)
            
            if endfor_match:
                lines_between = text_after_for[:endfor_match.end()].count('\n')
                end_line = start_line + lines_between
            else:
                end_line = 999999
            
            self.extracted_data["scoped"].append({
                "type": "for_fallback",
                "scope_range": {"start_line": start_line, "end_line": end_line},
                "vars": scoped_vars
            })

    def extract(self, template_code: str) -> dict:
        try:
            ast_tree = Environment().parse(template_code)
            self.visit(ast_tree)
        except Exception:
            self._regex_fallback(template_code)
            
        # Return the new structured dict containing globals and spatial scopes
        return self.extracted_data