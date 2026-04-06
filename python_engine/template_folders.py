"""
OmniJinja Template Path Extractor
---------------------------------
This module provides static analysis capabilities to discover Jinja2 template 
files within a Python project. It scans Python ASTs for Flask application 
initializations or Jinja2 FileSystemLoader configurations to determine the 
correct template root directories, and then extracts the relative paths of 
all available templates for IDE auto-completion (e.g., {% include "..." %}).
"""

import ast
import os
from typing import List

class TemplatePathExtractor(ast.NodeVisitor):
    """
    AST Visitor that detects template directories and extracts template file paths.
    
    Attributes:
        base_dir (str): The absolute path of the directory containing the analyzed Python file.
        template_paths (set): A collection of absolute paths to resolved template directories.
        allowed_extensions (tuple): File extensions recognized as Jinja2 templates.
        found_explicit_config (bool): Flag indicating if an explicit template path was found in the AST.
    """

    def __init__(self, current_file_path: str):
        """
        Initializes the extractor based on the location of the current Python file.
        
        Args:
            current_file_path (str): The absolute path of the Python script being analyzed.
        """
        self.base_dir = os.path.dirname(os.path.abspath(current_file_path))
        self.template_paths = set()
        self.allowed_extensions = ('.html', '.j2', '.jinja2', '.jinja')
        self.found_explicit_config = False

    def visit_Call(self, node: ast.Call):
        """
        Inspects function calls to identify Flask or Jinja2 environment initializations.
        
        It looks for:
        1. Flask app creation: `app = Flask(__name__, template_folder='...')`
        2. Jinja2 loader: `loader = FileSystemLoader('...')` or `FileSystemLoader(['...', '...'])`
        """
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            
            # Scenario 1: Flask Application Initialization
            if func_name == 'Flask':
                self.found_explicit_config = True
                folder_name = 'templates'  # Flask's default template folder name
                
                # Check if the user explicitly provided a 'template_folder' keyword argument
                for kw in node.keywords:
                    if kw.arg == 'template_folder' and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        folder_name = kw.value.value
                        
                abs_path = os.path.normpath(os.path.join(self.base_dir, folder_name))
                self.template_paths.add(abs_path)

            # Scenario 2: Native Jinja2 FileSystemLoader Initialization
            elif func_name == 'FileSystemLoader':
                self.found_explicit_config = True
                if node.args:
                    first_arg = node.args[0]
                    # Handle single string path: FileSystemLoader('templates')
                    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                        abs_path = os.path.normpath(os.path.join(self.base_dir, first_arg.value))
                        self.template_paths.add(abs_path)
                    # Handle list of paths: FileSystemLoader(['templates', 'other_templates'])
                    elif isinstance(first_arg, ast.List):
                        for element in first_arg.elts:
                            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                                abs_path = os.path.normpath(os.path.join(self.base_dir, element.value))
                                self.template_paths.add(abs_path)

        self.generic_visit(node)

    def get_template_files(self) -> List[str]:
        """
        Resolves the template directories and collects all valid template files.
        
        If no explicit configuration was found in the AST, it falls back to common 
        heuristic paths (e.g., './templates' or '../templates'). It then walks the 
        directories and calculates paths relative to the template root.
        
        Returns:
            List[str]: A sorted list of relative template paths (e.g., ['layouts/base.html', 'index.html']).
        """
        # Fallback heuristic: If AST analysis found no explicit config, try standard defaults
        if not self.found_explicit_config:
            default_path = os.path.normpath(os.path.join(self.base_dir, 'templates'))
            if os.path.exists(default_path) and os.path.isdir(default_path):
                self.template_paths.add(default_path)
            else:
                parent_default_path = os.path.normpath(os.path.join(self.base_dir, '..', 'templates'))
                if os.path.exists(parent_default_path) and os.path.isdir(parent_default_path):
                    self.template_paths.add(parent_default_path)

        template_files = set()
        
        # Walk through all identified template directories
        for folder_path in self.template_paths:
            if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
                continue
                
            for root, dirs, files in os.walk(folder_path):
                for file_name in files:
                    if file_name.endswith(self.allowed_extensions):
                        full_file_path = os.path.join(root, file_name)
                        
                        # Calculate the path relative to the template root directory
                        # This is critical because Jinja's {% include %} and {% extends %} 
                        # directives use relative paths, not absolute system paths.
                        jinja_rel_path = os.path.relpath(full_file_path, folder_path)
                        
                        # Normalize to forward slashes to ensure cross-platform compatibility 
                        # (Windows generates backslashes, but Jinja expects forward slashes).
                        jinja_rel_path = jinja_rel_path.replace('\\', '/')
                        
                        template_files.add(jinja_rel_path)
                        
        return sorted(list(template_files))