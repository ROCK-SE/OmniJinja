"""
OmniJinja Internal Symbol Extractor
----------------------------------
Extract variables introduced within the template, 
such as {% set %}, {% for %}, and macros, for use in completion and scope modeling.
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
            "__type__": "LoopObject",
            "index": {"__type__": "Integer"},
            "index0": {"__type__": "Integer"},
            "revindex": {"__type__": "Integer"},
            "revindex0": {"__type__": "Integer"},
            "first": {"__type__": "Boolean"},
            "last": {"__type__": "Boolean"},
            "length": {"__type__": "Integer"},
            "cycle": {
                "__type__": "Function",
                "signature": "cycle(...items)",
                "args": ["...items"]
            },
            "depth": {"__type__": "Integer"},
            "depth0": {"__type__": "Integer"},
            "previtem": {"__type__": "Any"},
            "nextitem": {"__type__": "Any"},
            "changed": {
                "__type__": "Function",
                "signature": "changed(*val)",
                "args": ["value"]
            }
        }

    def _extract_path(self, node) -> list:
        """Recursively converts an AST node path (e.g., user.id) into a list of strings."""
        if isinstance(node, nodes.Name): return [node.name]
        elif isinstance(node, nodes.Getattr):
            base = self._extract_path(node.node)
            return base + [node.attr] if base else []
        elif isinstance(node, nodes.Filter):
            return self._extract_path(node.node)
        elif isinstance(node, nodes.Call) and isinstance(node.node, nodes.Getattr):
            return self._extract_path(node.node.node)
        return []

    def _extract_target_names(self, target) -> list:
        if isinstance(target, nodes.Name):
            return [target.name]
        if isinstance(target, nodes.Tuple):
            return [item.name for item in target.items if isinstance(item, nodes.Name)]
        return []

    def _loop_target_schema(self, iter_node, iter_type_data: dict, target_count: int, target_index: int) -> dict:
        if target_count > 1:
            if isinstance(iter_node, nodes.Filter) and iter_node.name == "dictsort" and target_index == 0:
                return {"__type__": "String"}
            return {"__type__": "Any"}
        return iter_type_data if iter_type_data else {"__type__": "Any"}

    def _extract_macro_args(self, args) -> list:
        return [arg.name for arg in args if isinstance(arg, nodes.Name)]

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
        target_names = self._extract_target_names(node.target)
        for index, target_name in enumerate(target_names):
            local_scope[target_name] = self._loop_target_schema(node.iter, iter_type_data, len(target_names), index)
            
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

    def visit_Macro(self, node: nodes.Macro):
        arg_names = self._extract_macro_args(node.args)
        local_scope = {
            arg_name: {"__type__": "Any"}
            for arg_name in arg_names
        }

        self.extracted_data["scoped"].append({
            "type": "macro",
            "scope_range": {"start_line": node.lineno, "end_line": self._get_block_end_line(node)},
            "vars": local_scope
        })

        self.scope_stack.append(local_scope)
        for child in node.body:
            self.visit(child)
        self.scope_stack.pop()

    def _regex_fallback(self, template_code: str):
        """
        Regex-based recovery for incomplete or invalid ASTs.
        Ensures variables and dependencies are preserved when typing invalid syntax (e.g., {{  }}).
        """
        
        set_pattern = re.compile(r'\{%-?\s*set\s+([a-zA-Z0-9_]+)\s*=\s*([a-zA-Z0-9_.]+)')
        for match in set_pattern.finditer(template_code):
            var_name, path_str = match.groups()
            schema = self._resolve_schema(path_str.split('.'))
            
            start_line = template_code[:match.start()].count('\n') + 1
            schema["def_line"] = start_line
            
            self.extracted_data["globals"][var_name] = schema
            self.scope_stack[0][var_name] = schema
            
        for_pattern = re.compile(r'\{%-?\s*for\s+([a-zA-Z0-9_, \t]+?)\s+in\s+([a-zA-Z0-9_.]+)(?:\s*\|\s*([a-zA-Z0-9_]+))?')
        for match in for_pattern.finditer(template_code):
            target_str, path_str, filter_name = match.groups()
            target_names = [
                name.strip()
                for name in target_str.split(',')
                if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name.strip())
            ]
            iter_data = self._resolve_schema(path_str.split('.'), is_iterable=True)
            
            start_line = template_code[:match.start()].count('\n') + 1
            
            scoped_vars = {"loop": self.LOOP_PROPERTIES}
            for index, target_name in enumerate(target_names):
                if len(target_names) > 1:
                    scoped_vars[target_name] = {"__type__": "String"} if filter_name == "dictsort" and index == 0 else {"__type__": "Any"}
                else:
                    scoped_vars[target_name] = iter_data if iter_data else {"__type__": "Any"}
            
            text_after_for = template_code[match.end():]
            endfor_match = re.search(r'\{%-?\s*endfor\s*-?%\}', text_after_for)
            
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

        def _ensure_deps_fallback():
            if "dependencies" not in self.extracted_data:
                self.extracted_data["dependencies"] = {}

        extends_match = re.search(r'\{%-?\s*extends\s*[\'"]([^\'"]+)[\'"]\s*-?%\}', template_code)
        if extends_match:
            _ensure_deps_fallback()
            self.extracted_data["dependencies"]["extends"] = extends_match.group(1)

        include_pattern = re.compile(r'\{%-?\s*include\s*[\'"]([^\'"]+)[\'"]\s*-?%\}')
        includes = [m.group(1) for m in include_pattern.finditer(template_code)]
        if includes:
            _ensure_deps_fallback()
            if "includes" not in self.extracted_data["dependencies"]:
                self.extracted_data["dependencies"]["includes"] = []
            self.extracted_data["dependencies"]["includes"].extend(includes)

        import_pattern = re.compile(r'\{%-?\s*import\s*[\'"]([^\'"]+)[\'"]\s+as\s+([a-zA-Z0-9_]+)\s*-?%\}')
        for match in import_pattern.finditer(template_code):
            _ensure_deps_fallback()
            if "imports" not in self.extracted_data["dependencies"]:
                self.extracted_data["dependencies"]["imports"] = []
            self.extracted_data["dependencies"]["imports"].append({
                "type": "import",
                "template": match.group(1),
                "namespace": match.group(2)
            })

        from_import_pattern = re.compile(r'\{%-?\s*from\s*[\'"]([^\'"]+)[\'"]\s+import\s+(.+?)\s*-?%\}')
        for match in from_import_pattern.finditer(template_code):
            _ensure_deps_fallback()
            if "imports" not in self.extracted_data["dependencies"]:
                self.extracted_data["dependencies"]["imports"] = []
                
            template_name = match.group(1)
            names_str = match.group(2)
            
            names_dict = {}
            for part in names_str.split(','):
                part = part.strip()
                if ' as ' in part:
                    orig, alias = part.split(' as ', 1)
                    names_dict[orig.strip()] = alias.strip()
                elif part:
                    names_dict[part] = part
                    
            self.extracted_data["dependencies"]["imports"].append({
                "type": "from_import",
                "template": template_name,
                "names": names_dict
            })
        
        macro_pattern = re.compile(r'\{%-?\s*macro\s+([a-zA-Z0-9_]+)\s*\((.*?)\)\s*-?%\}')
        for match in macro_pattern.finditer(template_code):
            macro_name = match.group(1)
            args_str = match.group(2).strip()
            
            args_list = []
            if args_str:
                for arg in args_str.split(','):
                    clean_arg = arg.split('=')[0].strip()
                    if clean_arg:
                        args_list.append(clean_arg)
                        
            self.extracted_data[macro_name] = {
                "__type__": "Macro",
                "signature": f"{macro_name}({args_str})",
                "args": args_list,
                "docstring": "Macro (Fallback)",
                "def_line": template_code[:match.start()].count('\n') + 1
            }

            start_line = template_code[:match.start()].count('\n') + 1
            text_after_macro = template_code[match.end():]
            endmacro_match = re.search(r'\{%-?\s*endmacro\s*-?%\}', text_after_macro)
            if endmacro_match:
                lines_between = text_after_macro[:endmacro_match.end()].count('\n')
                end_line = start_line + lines_between
            else:
                end_line = 999999

            self.extracted_data["scoped"].append({
                "type": "macro_fallback",
                "scope_range": {"start_line": start_line, "end_line": end_line},
                "vars": {
                    arg_name: {"__type__": "Any"}
                    for arg_name in args_list
                }
            })

    def extract(self, template_code: str) -> dict:
        try:
            ast_tree = Environment().parse(template_code)
            self.visit(ast_tree)
        except Exception:
            self._regex_fallback(template_code)
            
        # Return the new structured dict containing globals and spatial scopes
        return self.extracted_data
    
    def _ensure_dependencies(self):
        if "dependencies" not in self.extracted_data:
            self.extracted_data["dependencies"] = {}

    def visit_Extends(self, node: nodes.Extends):
        if isinstance(node.template, nodes.Const):
            self._ensure_dependencies()
            self.extracted_data["dependencies"]["extends"] = node.template.value
        self.generic_visit(node)

    def visit_Include(self, node: nodes.Include):
        if isinstance(node.template, nodes.Const):
            self._ensure_dependencies()
            if "includes" not in self.extracted_data["dependencies"]:
                self.extracted_data["dependencies"]["includes"] = []
            self.extracted_data["dependencies"]["includes"].append(node.template.value)
        self.generic_visit(node)

    def visit_Import(self, node: nodes.Import):
        if isinstance(node.template, nodes.Const):
            self._ensure_dependencies()
            if "imports" not in self.extracted_data["dependencies"]:
                self.extracted_data["dependencies"]["imports"] = []
                
            self.extracted_data["dependencies"]["imports"].append({
                "type": "import",
                "template": node.template.value,
                "namespace": node.target
            })
        self.generic_visit(node)

    def visit_FromImport(self, node: nodes.FromImport):
        if isinstance(node.template, nodes.Const):
            self._ensure_dependencies()
            if "imports" not in self.extracted_data["dependencies"]:
                self.extracted_data["dependencies"]["imports"] = []
            
            names_dict = {}
            for name, alias in node.names:
                names_dict[name] = alias if alias else name
                
            self.extracted_data["dependencies"]["imports"].append({
                "type": "from_import",
                "template": node.template.value,
                "names": names_dict
            })
        self.generic_visit(node)
