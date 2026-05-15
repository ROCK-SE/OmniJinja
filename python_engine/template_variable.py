from jinja2 import Environment, nodes
from jinja2.visitor import NodeVisitor
'''
Extract the data that actually needs to be provided by Python from the template, 
and use extension.ts to perform a reverse check to see if render_template has been passed completely.
'''

STANDARD_METHODS = {
    'upper', 'lower', 'capitalize', 'replace', 'split', 'strip', 'startswith', 'endswith',
    'keys', 'values', 'items', 'get', 'append', 'extend', 'pop', 'index', 'count', 'format'
}

class JinjaExternalVariableExtractor(NodeVisitor):
    def __init__(self):
        self.variables_model = {}
        self.scope_stack = [{}]
        
    def _extract_path(self, node) -> list:
        if isinstance(node, nodes.Name):
            return [node.name]
        elif isinstance(node, (nodes.Getattr, nodes.Getitem)):
            base_path = self._extract_path(node.node)
            if not base_path: return []
            if isinstance(node, nodes.Getitem):
                if isinstance(node.arg, nodes.Const) and isinstance(node.arg.value, str):
                    return base_path + [node.arg.value]
                return base_path 
            elif isinstance(node, nodes.Getattr):
                if node.attr not in STANDARD_METHODS:
                    return base_path + [node.attr]
                return base_path
        return []

    def _record_path(self, path: list, is_callable: bool = False):
        if not path: return
        base_var = path[0]
        target_dict = None
        found_in_scope = False
        
        for scope in reversed(self.scope_stack):
            if base_var in scope:
                target_dict = scope[base_var]
                found_in_scope = True
                break
                
        if not found_in_scope:
            if base_var not in self.variables_model:
                self.variables_model[base_var] = {}
            target_dict = self.variables_model[base_var]
            
        if target_dict is None: return
            
        current = target_dict
        for attr in path[1:]:
            if attr not in current:
                current[attr] = {}
            current = current[attr]
            
        if is_callable:
            current["__is_callable__"] = True

    def visit_Name(self, node: nodes.Name):
        if node.ctx == 'load': 
            self._record_path([node.name])
            
    def visit_Getattr(self, node: nodes.Getattr):
        self._record_path(self._extract_path(node))
        self.generic_visit(node)
        
    def visit_Getitem(self, node: nodes.Getitem):
        self._record_path(self._extract_path(node))
        self.generic_visit(node)
        
    def visit_Call(self, node: nodes.Call):
        if isinstance(node.node, (nodes.Getattr, nodes.Name)):
            self._record_path(self._extract_path(node.node), is_callable=True)
        for arg in node.args: self.visit(arg)
        for kwarg in node.kwargs: self.visit(kwarg.value)

    def visit_Assign(self, node: nodes.Assign):
        self.visit(node.node)
        if isinstance(node.target, nodes.Name):
            self.scope_stack[-1][node.target.name] = None
            
    def visit_Macro(self, node: nodes.Macro):
        self.scope_stack[-1][node.name] = None
        local_scope = {}
        for arg in node.args:
            if isinstance(arg, nodes.Name): local_scope[arg.name] = None
        self.scope_stack.append(local_scope)
        for child in node.body: self.visit(child)
        self.scope_stack.pop()

    def visit_For(self, node: nodes.For):
        iter_path = self._extract_path(node.iter)
        self._record_path(iter_path)
        element_sandbox = {}
        
        if iter_path:
            base_var = iter_path[0]
            target_dict = None
            for scope in reversed(self.scope_stack):
                if base_var in scope:
                    target_dict = scope[base_var]
                    break
            
            if target_dict is None and base_var in self.variables_model:
                target_dict = self.variables_model[base_var]
                
            if target_dict is not None:
                current = target_dict
                for attr in iter_path[1:]:
                    if attr in current: current = current[attr]
                current["__is_iterable__"] = True
                if "__element__" not in current: current["__element__"] = {}
                element_sandbox = current["__element__"]

        local_scope = {"loop": None} 
        if isinstance(node.target, nodes.Name):
            local_scope[node.target.name] = element_sandbox
        self.scope_stack.append(local_scope)
        for child in node.body: self.visit(child)
        self.scope_stack.pop()

def clean_and_format_model(obj):
    if isinstance(obj, dict):
        if obj.get("__is_iterable__"):
            element_data = obj.get("__element__", {})
            return {
                "__type__": "Iterable",
                "__is_iterable__": True,
                "__element__": clean_and_format_model(element_data)
            }
        cleaned = {}
        for key, value in obj.items():
            if not key.startswith("__"):
                cleaned[key] = clean_and_format_model(value)
        if obj.get("__is_callable__"):
            cleaned["__is_callable__"] = True
        return cleaned if cleaned or obj.get("__is_callable__") else {"__type__": "Any"}
    return obj

def extract_external_requirements(template_source: str) -> dict:
    env = Environment()
    try:
        ast = env.parse(template_source)
        visitor = JinjaExternalVariableExtractor()
        visitor.visit(ast)
        return clean_and_format_model(visitor.variables_model)
    except: return {}
    
    
