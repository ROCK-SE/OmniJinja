"""
OmniJinja Macro Signature Extractor
----------------------------------
This module provides functionality to parse Jinja2 templates, identify 
defined macros, and extract their argument signatures. It converts these 
macros into a function-like schema that the VS Code extension uses for 
auto-completion and hover hints.
"""
import json
from jinja2 import Environment, nodes

class JinjaMacroExtractor:
    def __init__(self):
        self.env = Environment()

    def extract_macros(self, template_code: str) -> dict:
        
        macros = {}
        try:
            ast = self.env.parse(template_code)
        except Exception:
            return macros 

        for node in ast.find_all(nodes.Macro):
            macro_name = node.name
            args = [arg.name for arg in node.args if isinstance(arg, nodes.Name)]
            
            macros[macro_name] = {
                "__type__": "Macro",
                "args": args,
                "signature": f"{macro_name}({', '.join(args)})",
                "docstring": f"Jinja Macro: {macro_name}" 
            }
            
        return macros
    
    def get_macros_as_json(self, template_code: str) -> str:
        return json.dumps(self.extract_macros(template_code), indent=4, ensure_ascii=False)

