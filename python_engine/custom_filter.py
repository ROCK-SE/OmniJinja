"""
OmniJinja Custom Filter Extractor
---------------------------------
This module implements an AST visitor to identify and 
extract custom Jinja2 filters from Python source code (specifically Flask apps).
It supports filters registered via decorators or direct dictionary assignments.
"""
import ast
import json

class CustomFilterExtractor(ast.NodeVisitor):
    def __init__(self):
        self.custom_filters = []
        self._func_registry = {}

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """
        Processes function definitions to detect filters registered via decorators.
        
        This method captures function metadata and checks for decorators like 
        '@app.template_filter()'. It also records the definition line number 
        to support "Go to Definition" features in the IDE.
        
        Args:
            node (ast.FunctionDef): The AST node representing a function definition.
        """
        args = [arg.arg for arg in node.args.args]
        docstring = ast.get_docstring(node) or ""
        self._func_registry[node.name] = {"args": args, "doc": docstring, "line": node.lineno}

        for decorator in node.decorator_list:
            is_filter = False
            filter_name = None

            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute) and decorator.func.attr == 'template_filter':
                    is_filter = True
                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                        filter_name = decorator.args[0].value
                    else:
                        filter_name = node.name
            elif isinstance(decorator, ast.Attribute):
                if decorator.attr == 'template_filter':
                    is_filter = True
                    filter_name = node.name

            if is_filter:
                self._record_filter(filter_name, args, docstring, node.lineno)
        
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        """
        Processes assignments to detect filters registered via dictionary mapping.
        
        Handles patterns like: app.jinja_env.filters['my_filter'] = my_func_name
        
        Args:
            node (ast.Assign): The AST node representing an assignment statement.
        """
        for target in node.targets:
            if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant):
                if isinstance(target.value, ast.Attribute) and target.value.attr == 'filters':
                    if isinstance(node.value, ast.Name):
                        filter_name = target.slice.value
                        func_name = node.value.id
                        
                        func_info = self._func_registry.get(func_name, {"args": ["value"], "doc": "", "line": 1})
                        self._record_filter(filter_name, func_info["args"], func_info["doc"], func_info["line"])
                        
        self.generic_visit(node)

    def _record_filter(self, filter_name, args, docstring, line_num):
        if any(f['name'] == filter_name for f in self.custom_filters):
            return
            
        display_args = args[1:] if len(args) > 0 else []
        signature = f"{filter_name}({', '.join(display_args)})" if display_args else filter_name
            
        self.custom_filters.append({
            "name": filter_name,
            "args": display_args,
            "signature": signature,
            "docstring": docstring,
            "line": line_num  
        })

    def get_filters_as_json(self) -> str:
        return json.dumps(self.custom_filters, indent=4, ensure_ascii=False)