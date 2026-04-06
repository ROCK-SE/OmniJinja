"""
OmniJinja Template Block Extractor
---------------------------------
This module provides logic for tracing Jinja2 template inheritance chains.
It identifies 'extends' tags and recursively crawls through parent templates
to extract block names available for overriding in the current child template.
"""

import os
from pathlib import Path
from jinja2 import Environment, nodes

class JinjaBlockExtractor:
    """
    Analyzes Jinja2 template inheritance to provide block name completion.
    
    Attributes:
        template_dir (Optional[Path]): The base directory where templates are located.
        env (Environment): The Jinja2 environment used for parsing ASTs.
    """
    def __init__(self, template_dir: str):
        self.template_dir = Path(template_dir) if template_dir else None
        self.env = Environment()

    def _read_template(self, rel_path: str) -> str:
        
        if not self.template_dir:
            return ""
        full_path = self.template_dir / rel_path
        if full_path.exists() and full_path.is_file():
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
        return ""

    def get_inherited_blocks(self, current_template_code: str) -> list:
        """
        Traces the inheritance chain upward to find all overridable blocks.
        
        This method parses the 'extends' tag of the current template and 
        recursively visits all ancestors to collect every unique block name.
        
        Args:
            current_template_code (str): The source code of the active template.
            
        Returns:
            List[str]: A sorted list of unique block names found in the hierarchy.
        """
        blocks = set()
        try:
            ast = self.env.parse(current_template_code)
        except Exception:
            return list(blocks)
            
        extends_node = next(ast.find_all(nodes.Extends), None)
        if not extends_node or not isinstance(extends_node.template, nodes.Const):
            return list(blocks)
            
        parent_rel_path = extends_node.template.value 
        visited_templates = set() 
        
        while parent_rel_path and parent_rel_path not in visited_templates:
            visited_templates.add(parent_rel_path)
            parent_code = self._read_template(parent_rel_path)
            if not parent_code:
                break
                
            try:
                parent_ast = self.env.parse(parent_code)
                for block_node in parent_ast.find_all(nodes.Block):
                    blocks.add(block_node.name)
                    
                parent_extends_node = next(parent_ast.find_all(nodes.Extends), None)
                if parent_extends_node and isinstance(parent_extends_node.template, nodes.Const):
                    parent_rel_path = parent_extends_node.template.value
                else:
                    parent_rel_path = None
            except Exception:
                break
                
        return sorted(list(blocks))

