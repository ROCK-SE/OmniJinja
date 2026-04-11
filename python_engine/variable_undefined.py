"""
OmniJinja Semantic Linter
-------------------------
This module provides a static analysis visitor that checks for undefined variables 
and invalid property accesses within Jinja2 templates. 

Unlike the structural syntax detector (which emits Errors), this linter evaluates 
the logical context based on the Python backend schema and emits Warnings (yellow 
squiggles) for missing or mismatched variables.
"""

from jinja2 import Environment, nodes
from jinja2.visitor import NodeVisitor
from typing import List, Dict, Any

class JinjaUndefinedLinter(NodeVisitor):
    """
    An AST Visitor that traverses Jinja2 templates to lint variable scoping.
    
    It maintains a scope stack to accurately track global variables (passed from Python),
    local variables (created via {% set %}), loop variables, and macro arguments.
    
    Attributes:
        backend_schema (Dict): The global context map exported by the Python backend.
        diagnostics (List[Dict]): A collection of detected warning payloads.
        scope_stack (List[Dict]): A stack of dictionaries representing variable scopes.
        BUILTIN_GLOBALS (Set[str]): A set of Jinja2 built-in global functions/variables.
    """

    def __init__(self, backend_schema: dict):
        """
        Initializes the linter with the global backend schema.
        """
        self.backend_schema = backend_schema or {}
        self.diagnostics: List[Dict[str, Any]] = []
        
        # Initialize the scope stack with the global backend context at the base
        self.scope_stack = [self.backend_schema.copy()]
        
        # Standard Jinja2 built-in globals that should never trigger an 'undefined' warning
        self.BUILTIN_GLOBALS = {'range', 'dict', 'lipsum', 'super', 'cycler', 'joiner', 'namespace'}

    def _extract_path(self, node: nodes.Node) -> list:
        """
        Recursively extracts an attribute access path into a list of strings.
        Example: user.profile.name -> ['user', 'profile', 'name']
        """
        if isinstance(node, nodes.Name): 
            return [node.name]
        elif isinstance(node, nodes.Getattr):
            base = self._extract_path(node.node)
            return base + [node.attr] if base else []
        return []

    def _check_undefined(self, path: list, lineno: int):
        """
        Validates if a variable or its property path exists within the current scope.
        
        Args:
            path (list): The variable resolution path (e.g., ['user', 'id']).
            lineno (int): The line number where the variable is accessed.
        """
        if not path: 
            return
            
        base_var = path[0]
        if base_var in self.BUILTIN_GLOBALS: 
            return

        # Search for the base variable from the innermost scope (top of stack) to the outermost
        found_in_scope = None
        for scope in reversed(self.scope_stack):
            if base_var in scope:
                found_in_scope = scope
                break
                
        if found_in_scope is None:
            # Deliberately downgraded to 'warning' severity.
            # In dynamic templates, variables might be injected at runtime outside the parsed schema.
            self.diagnostics.append({
                "line": lineno, 
                "message": f"⚠️ Undefined Warning: '{base_var}' is not defined in the current context.", 
                "severity": "warning"
            })
            return

        current_level = found_in_scope[base_var]
        
        # Traverse the property path to ensure nested attributes exist
        for i in range(1, len(path)):
            attr = path[i]
            parent_path = ".".join(str(p) for p in path[:i])
            
            # Check if user is trying to access a property directly on an Iterable (List/Set)
            if isinstance(current_level, list) or (isinstance(current_level, dict) and current_level.get("__is_iterable__")):
                self.diagnostics.append({
                    "line": lineno, 
                    "message": f"⚠️ Type Warning: '{parent_path}' is an Iterable/Collection. You cannot directly access '{attr}'.", 
                    "severity": "warning"
                })
                return

            if isinstance(current_level, dict):
                if attr in current_level: 
                    current_level = current_level[attr]
                else:
                    # Ignore arbitrary property access on purely generic objects
                    if "__type__" in current_level and len(current_level) == 1: 
                        return
                        
                    self.diagnostics.append({
                        "line": lineno, 
                        "message": f"⚠️ Property Warning: '{attr}' is not a known property of '{parent_path}'.", 
                        "severity": "warning"
                    })
                    return

    def _check_iterable(self, node: nodes.Node, lineno: int):
        """
        Validates that the given node (variable/expression) is iterable.
        Used for checking for-loop iteration expressions.
        
        Args:
            node (nodes.Node): The AST node representing the value being iterated over.
            lineno (int): The line number where the for-loop is located.
        """
        # Extract the variable path being iterated over
        path = self._extract_path(node)
        if not path:
            # Complex expressions like literals or operations - assume they're valid
            return
        
        base_var = path[0]
        if base_var in self.BUILTIN_GLOBALS:
            # Built-in functions like range() are iterable
            return

        # Search for the base variable in scope
        found_in_scope = None
        for scope in reversed(self.scope_stack):
            if base_var in scope:
                found_in_scope = scope
                break
        
        if found_in_scope is None:
            # Variable is undefined, but that's already caught by _check_undefined
            return

        # Get the variable value and traverse the property path if needed
        current_level = found_in_scope[base_var]
        
        for i in range(1, len(path)):
            attr = path[i]
            if isinstance(current_level, dict):
                if attr in current_level:
                    current_level = current_level[attr]
                else:
                    # Property doesn't exist - skip iterable check
                    return
            else:
                # Can't traverse further
                return
        
        # Now check if current_level is iterable
        is_iterable = False
        
        if isinstance(current_level, list):
            # Lists are iterable
            is_iterable = True
        elif isinstance(current_level, dict):
            # Check __is_iterable__ marker
            if current_level.get("__is_iterable__"):
                is_iterable = True
        
        if not is_iterable:
            # Get the variable name for the error message
            var_name = ".".join(str(p) for p in path)
            type_info = ""
            if isinstance(current_level, dict) and "__type__" in current_level:
                type_info = f" (of type {current_level['__type__']})"
            
            self.diagnostics.append({
                "line": lineno, 
                "message": f"⚠️ Type Warning: You iterate over a variable '{var_name}'{type_info} in Jinja that isn't actually an Iterable in Python.", 
                "severity": "warning"
            })

    def visit_Assign(self, node: nodes.Assign):
        """Tracks local variables created via {% set var = ... %}."""
        self.visit(node.node)
        if isinstance(node.target, nodes.Name):
            # Inject the new variable into the current (innermost) scope
            self.scope_stack[-1][node.target.name] = {"__type__": "Any"}

    def visit_For(self, node: nodes.For):
        """
        Manages scope for {% for %} loops. 
        Pushes a new local scope containing the loop variable and the built-in 'loop' object.
        Also validates that the iterated value is actually iterable.
        """
        # Check if the iterated value is actually iterable
        self._check_iterable(node.iter, node.lineno)
        
        self.visit(node.iter)
        
        local_scope = {"loop": {"__type__": "LoopObject"}}
        if isinstance(node.target, nodes.Name):
            local_scope[node.target.name] = {"__type__": "Any"}
            
        self.scope_stack.append(local_scope)
        for child in node.body: 
            self.visit(child)
        self.scope_stack.pop()

    def visit_Macro(self, node: nodes.Macro):
        """
        Manages scope for {% macro %} definitions.
        Registers the macro in the current scope, and pushes a new scope for its arguments.
        """
        self.scope_stack[-1][node.name] = {"__type__": "Function"}
        
        local_scope = {}
        for arg in node.args:
            if isinstance(arg, nodes.Name): 
                local_scope[arg.name] = {"__type__": "Any"}
                
        self.scope_stack.append(local_scope)
        for child in node.body: 
            self.visit(child)
        self.scope_stack.pop()

    def visit_Name(self, node: nodes.Name):
        """Triggers undefined checks when a bare variable is loaded/read."""
        if node.ctx == 'load': 
            self._check_undefined([node.name], node.lineno)

    def visit_Getattr(self, node: nodes.Getattr):
        """Triggers undefined checks when a property path is accessed."""
        path = self._extract_path(node)
        if path: 
            self._check_undefined(path, node.lineno)

    def lint(self, template_code: str) -> list:
        """
        Executes the linting process on a raw Jinja2 template string.
        
        Args:
            template_code (str): The Jinja2 template source code.
            
        Returns:
            list: A list of diagnostic dictionary objects formatted for the IDE.
        """
        try:
            ast_tree = Environment().parse(template_code)
            self.visit(ast_tree)
        except Exception :
            pass
            
        return self.diagnostics