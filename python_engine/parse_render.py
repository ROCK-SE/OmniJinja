"""
OmniJinja Flask Render Parser
-----------------------------
This module provides a static analysis tool based on Python's Abstract Syntax Tree (AST).
It scans Python backend code (specifically Flask applications) to detect where 
templates are rendered and extracts the variables (context) passed to them.

This bridges the gap between Python backend logic and Jinja2 frontend intelligence,
preparing precise coordinate data (line/col) for the Jedi inference engine.
"""

import ast
from collections import defaultdict
from typing import List, Dict, Any

class FlaskTemplateVisitor(ast.NodeVisitor):
    """
    An AST visitor that tracks variable assignments and extracts context data 
    from 'render_template' and '.render()' calls.
    
    Attributes:
        ast (ast.AST): The parsed abstract syntax tree of the source code.
        global_context (dict): Variables injected globally via @context_processor.
        current_function (str): Tracks the scope of the function currently being visited.
        dict_assignments (defaultdict): Tracks local dictionary assignments to support **kwargs unpacking.
                                        Structure: { "function_name": { "dict_name": { "key": coordinate_info } } }
        render_calls (list): A list accumulating all detected render calls and their context payloads.
    """

    def __init__(self, code: str):
        """
        Initializes the visitor and attempts to parse the provided source code.
        
        Args:
            code (str): The raw Python source code to analyze.
        """
        try:
            self.ast = ast.parse(code)
        except SyntaxError:
            try:
                self.ast = ast.parse(code)
            except Exception:
                self.ast = None
            
        self.global_context = {} 
        self.current_function = None 
        self.dict_assignments = defaultdict(dict) 
        self.render_calls = [] 

    def get_results(self) -> List[Dict[str, Any]]:
        """
        Executes the AST traversal and returns the formatted extraction results.
        
        Returns:
            List[Dict]: A list of dictionaries, each containing the 'template' name,
                        the 'context' variables passed to it, and the 'render_line'.
        """
        if not self.ast:
            return []
            
        # Trigger the recursive AST traversal
        self.visit(self.ast) 
        
        formatted_results = []
        for call in self.render_calls:
            formatted_results.append({
                "template": call["template"],
                "context": call["context"],
                "render_line": call["render_line"] # The line number of the render call
            })
        return formatted_results

    def _prepare_for_jedi(self, node: ast.AST) -> dict:
        """
        Extracts the string representation and grid coordinates of an AST node.
        This metadata is specifically formatted to feed into the Jedi inference engine.
        
        Args:
            node (ast.AST): The Python AST node representing a variable/value.
            
        Returns:
            dict: Contains 'code' (string), 'line' (int), and 'column' (int).
        """
        try:
            # ast.unparse converts an AST node back into a raw code string
            # e.g., converting an ast.Name node back to the string "user_obj"
            code_str = ast.unparse(node)
        except Exception:
            code_str = "<complex_expr>"
            
        return {
            "code": code_str,
            "line": getattr(node, 'lineno', None),      # Required by Jedi for location
            "column": getattr(node, 'col_offset', None) # Required by Jedi for location
        }
        
    def is_render_call(self, node: ast.Call) -> bool:
        """
        Determines if an AST Call node represents a template rendering execution.
        Covers both Flask (render_template) and native Jinja2 (template.render).
        """
        if isinstance(node.func, ast.Name) and node.func.id == 'render_template':
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'render':
            return True
        return False

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """
        Visits function definitions to track current scope and capture global 
        context processors.
        """
        # Scan function decorators for global context injection (Flask @app.context_processor)
        for deco in node.decorator_list:
            if getattr(deco, 'attr', '') == 'context_processor' or getattr(deco, 'id', '') == 'context_processor':
                for stmt in node.body:
                    # Look for return statements that output a dictionary
                    if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Dict):
                        for k, v in zip(stmt.value.keys, stmt.value.values):
                            if isinstance(k, ast.Constant):
                                self.global_context[k.value] = self._prepare_for_jedi(v)

        # State management for nested scoping
        prev_function = self.current_function 
        self.current_function = node.name 
        
        # Continue traversing the function body
        self.generic_visit(node) 
        
        # Restore the previous scope state after exiting the function
        self.current_function = prev_function 

    def visit_Assign(self, node: ast.Assign):
        """
        Visits variable assignments to track local dictionaries, which is crucial 
        for resolving template calls that use kwargs unpacking (e.g., **context).
        """
        # Check if we are inside a function and assigning a dictionary literal
        if self.current_function and isinstance(node.value, ast.Dict):
            for target in node.targets:
                # Ensure the assignment target is a standard variable name
                if isinstance(target, ast.Name):
                    dict_items = {}
                    # Iterate through the dictionary's key-value pairs
                    for k, v in zip(node.value.keys, node.value.values):
                        if isinstance(k, ast.Constant):
                            # Package the value's Jedi coordinates and store it temporarily
                            dict_items[k.value] = self._prepare_for_jedi(v)
                            
                    # Register this dictionary under the current function's scope
                    self.dict_assignments[self.current_function][target.id] = dict_items
                    
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """
        Visits function calls to detect template rendering and extract context payloads.
        This handles direct arguments, keyword arguments, and dictionary unpacking.
        """
        # Skip calls that are not template rendering functions
        if not self.is_render_call(node):
            self.generic_visit(node)
            return

        # Extract the template name (usually the first positional argument)
        template_name = "Unknown"
        if node.args and isinstance(node.args[0], ast.Constant):
            template_name = node.args[0].value
            
        # Initialize context with variables from the global @context_processor
        context_data = dict(self.global_context)
        
        # Case 1: Unnamed dictionary argument -> template.render({"user": user})
        if node.args and isinstance(node.args[0], ast.Dict):
            for k, v in zip(node.args[0].keys, node.args[0].values):
                if isinstance(k, ast.Constant):
                    context_data[k.value] = self._prepare_for_jedi(v)
                    
        # Case 2 & 3: Iterate through keyword arguments
        for keyword in node.keywords:
            if keyword.arg:
                # Case 2: Direct kwargs -> render_template(user=user)
                # keyword.arg is the target parameter, keyword.value is the AST node of the passed variable
                context_data[keyword.arg] = self._prepare_for_jedi(keyword.value)
            else:
                # Case 3: Dictionary unpacking -> render_template(**context)
                # For **kwargs unpacking, keyword.arg is always None
                if isinstance(keyword.value, ast.Name):
                    dict_name = keyword.value.id
                    # Lookup the tracked dictionary in the current function scope
                    if self.current_function and dict_name in self.dict_assignments[self.current_function]:
                        context_data.update(self.dict_assignments[self.current_function][dict_name])
                        
                # Handle inline dictionary unpacking -> render_template(**{"page_title": "Home"})
                elif isinstance(keyword.value, ast.Dict):
                    for k, v in zip(keyword.value.keys, keyword.value.values):
                        if isinstance(k, ast.Constant):
                            context_data[k.value] = self._prepare_for_jedi(v)

        # Record the successful extraction of this render call
        self.render_calls.append({
            "template": template_name,
            "context": context_data,
            "render_line": getattr(node, 'lineno', None) 
        })
        
        self.generic_visit(node)