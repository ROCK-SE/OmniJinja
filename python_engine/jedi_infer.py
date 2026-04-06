"""
OmniJinja Jedi Type Inference Engine
------------------------------------
This module leverages the Jedi library to perform deep static analysis on 
Python source code. It extracts type information, properties, and method 
signatures to provide rich intellisense for variables passed into Jinja2 templates.
"""
import jedi

class JediPropertyExtractor:
    def __init__(self, source_code: str, max_depth: int = 2):
        """
        Initializes the extractor with source code and recursion limits.
        
        Args:
            source_code (str): The Python source to be analyzed.
            max_depth (int): Depth limit for exploring nested attributes.
        """
        self.source_code = source_code
        self.script = jedi.Script(source_code) 
        self.max_depth = max_depth
        
        self.native_types = {
            'str': '<String>', 'list': '<List>', 'int': '<Integer>', 
            'float': '<Float>', 'bool': '<Boolean>', 'dict': '<Dictionary>',
            'tuple': '<Tuple>', 'set': '<Set>'
        }

    def _get_func_info(self, obj_with_doc, func_name) -> dict:
        """
        Extracts metadata from a function or method object.
        
        Args:
            obj_with_doc: A Jedi Name or Value object with documentation.
            func_name (str): The name of the function.
            
        Returns:
            dict: Metadata including signature, arguments, and docstrings.
        """
        raw_doc = obj_with_doc.docstring()
        clean_doc = self._clean_docstring(raw_doc, func_name)
        args = []
        sig_str = f"{func_name}()"
        
        try:
            if hasattr(obj_with_doc, 'get_signatures'):
                sigs = obj_with_doc.get_signatures()
                if sigs:
                    sig = sigs[0]
                    args = [p.name for p in sig.params if p.name != 'self']
                    sig_str = f"{func_name}({', '.join(args)})"
        except Exception:
            pass
            
        return {
            "__type__": "Function",
            "docstring": clean_doc,
            "def_line": getattr(obj_with_doc, 'line', None),
            "args": args,
            "signature": sig_str
        }

    def _infer_type_name(self, original_line: int, original_col: int, original_code_str: str, current_expr: str) -> str:
        """
        Infers the class name of an expression at a specific source location.
        
        Args:
            original_line: Line number in original source.
            original_col: Column offset in original source.
            original_code_str: The original variable/expression name.
            current_expr: The temporary expression to probe.
            
        Returns:
            str: The resolved class name or 'Object' if unresolved.
        """
        if original_line is None or original_col is None: return "Object"
        try:
            lines = self.source_code.split('\n')
            target_line = lines[original_line - 1]
            start_col = original_col
            
            new_line_str = target_line[:start_col] + current_expr + target_line[start_col + len(original_code_str):]
            new_lines = lines[:original_line - 1] + [new_line_str] + lines[original_line:]
            probe_script = jedi.Script("\n".join(new_lines))
            
            infs = probe_script.infer(original_line, start_col + len(current_expr))
            if infs:
                return infs[0].name if infs[0].name else "Object"
        except Exception:
            pass
        return "Object"

    def enrich_template_context(self, ast_results: list) -> list:
        """
        The primary public method to resolve types for all template variables.
        
        Takes the raw coordinates from AST analysis and uses Jedi to determine 
        the actual object structure for each variable.
        
        Args:
            ast_results (list): Output from the initial AST-based render_template scanner.
            
        Returns:
            list: The same list enriched with deep type schemas and property maps.
        """
        final_results = []
        for call in ast_results:
            enriched_context = {}
            for var_name, var_info in call['context'].items():
                line = var_info.get('line')
                column = var_info.get('column')
                code_str = var_info.get('code', '') 
                
                if not code_str:
                    enriched_context[var_name] = "<Unknown>"
                    continue
                if code_str.startswith("'") or code_str.startswith('"') or code_str.isdigit():
                    enriched_context[var_name] = code_str
                    continue

                try:
                    inferences = self.script.infer(line, column)
                    if inferences:
                        inf = inferences[0]
                        if inf.name in ['list', 'tuple', 'set']:
                            inner_expr = f"list({code_str})[0]"
                            inner_props = self._get_properties(line, column, code_str, inner_expr, 1)
                            if inner_props:
                                element_class_name = self._infer_type_name(line, column, code_str, inner_expr)
                                enriched_context[var_name] = {
                                    "__type__": inf.name.capitalize(), # "List", "Set", "Tuple"
                                    "__is_iterable__": True,
                                    "__element__": {
                                        "__type__": element_class_name,
                                        "def_line": getattr(inf, 'line', None),
                                        **inner_props
                                    }
                                }
                            else:
                                enriched_context[var_name] = f"{code_str}{self.native_types[inf.name]}"
                        
                        elif inf.name in self.native_types:
                            enriched_context[var_name] = f"{code_str}{self.native_types[inf.name]}"
                        
                        elif inf.type in ['instance', 'class', 'module']:
                            props = self._get_properties(line, column, code_str, code_str, 1)
                            class_name = inf.name if inf.name else "Object"
                            
                            is_iterable = class_name.endswith('Query') or class_name.endswith('Set')
                            
                            if props:
                                enriched_context[var_name] = {
                                    "__type__": class_name, 
                                    "__is_iterable__": is_iterable,
                                    "def_line": getattr(inf, 'line', None), 
                                    **props
                                }
                            else:
                                enriched_context[var_name] = {
                                    "__type__": class_name, 
                                    "__is_iterable__": is_iterable,
                                    "def_line": getattr(inf, 'line', None)
                                }
                        else:
                            enriched_context[var_name] = f"{code_str}<{inf.type.capitalize()}>"
                    else:
                        enriched_context[var_name] = code_str
                except Exception as e:
                    enriched_context[var_name] = f"{code_str}<Inference Failed>"
                    
            final_results.append({
                "template": call["template"],
                "context": enriched_context
            })
        return final_results

    def _clean_docstring(self, raw_doc: str, func_name: str) -> str:
        if not raw_doc: return ""
        if "\n\n" in raw_doc: return raw_doc.split("\n\n", 1)[-1].strip()
        if raw_doc.startswith(func_name + "("): return ""
        return raw_doc.strip()

    def _get_properties(self, original_line: int, original_col: int, original_code_str: str, current_expr: str, current_depth: int) -> dict:
        """
        Recursively discovers properties and methods of an object.
        Uses Jedi's completion engine by simulating a 'dot' access in a temporary buffer.
        """
        if current_depth > self.max_depth: return {}
        if original_line is None or original_col is None: return {}
            
        lines = self.source_code.split('\n')
        if original_line < 1 or original_line > len(lines): return {}
        
        target_line = lines[original_line - 1]
        start_col = original_col
        
        new_line_str = target_line[:start_col] + current_expr + "." + target_line[start_col + len(original_code_str):]
        new_lines = lines[:original_line - 1] + [new_line_str] + lines[original_line:]
        probe_code = "\n".join(new_lines)
        
        probe_line_num = original_line
        probe_column_num = start_col + len(current_expr) + 1
        
        probe_script = jedi.Script(probe_code)
        completions = probe_script.complete(probe_line_num, probe_column_num)
        
        properties = {}
        for c in completions:
            if c.type in ['class', 'module'] or c.name.startswith('_'):
                continue
                
            inferences = c.infer()
            if inferences:
                inf = inferences[0]
                if inf.name in self.native_types:
                    properties[c.name] = self.native_types[inf.name]
                elif inf.type in ['instance', 'class']:
                    next_expr = f"{current_expr}.{c.name}"
                    sub_props = self._get_properties(original_line, original_col, original_code_str, next_expr, current_depth + 1)
                    class_name = inf.name if inf.name else "Object"
                    if sub_props:
                        properties[c.name] = {"__type__": class_name, "def_line": getattr(inf, 'line', None), **sub_props}
                    else:
                        properties[c.name] = {"__type__": class_name, "def_line": getattr(inf, 'line', None)}
                elif inf.type == 'function':
                    properties[c.name] = self._get_func_info(inf, c.name)
                else:
                    properties[c.name] = f"<{inf.type.capitalize()}>"
            else:
                if c.type == 'function':
                    properties[c.name] = self._get_func_info(c, c.name)
                else:
                    properties[c.name] = "<Property>"
                
        return properties