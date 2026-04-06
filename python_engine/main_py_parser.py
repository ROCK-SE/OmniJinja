"""
OmniJinja Python Source Parser (Backend Orchestrator)
---------------------------------------------------
This script acts as the primary orchestrator for analyzing Python backend files 
(typically Flask applications). It coordinates 5 core extraction modules to 
build a comprehensive JSON schema that the VS Code frontend uses for Jinja2 
auto-completion, hover hints, and type inference.
"""

import sys
import os
import json
import ast

try:
    from import_infer import has_flask_or_jinja_import
except ImportError:
    def has_flask_or_jinja_import(code: str) -> bool:
        return 'flask' in code.lower() or 'jinja' in code.lower()

from parse_render import FlaskTemplateVisitor
from jedi_infer import JediPropertyExtractor
from template_folders import TemplatePathExtractor
from custom_filter import CustomFilterExtractor

def main():

    if len(sys.argv) < 3:
        print("Usage: python main_py_parser.py <target_py_file> <workspace_root>")
        sys.exit(1)

    target_py_file = sys.argv[1]
    workspace_root = sys.argv[2]

    if not os.path.exists(target_py_file):
        print(f"File not found: {target_py_file}")
        sys.exit(1)

    try:
        with open(target_py_file, 'r', encoding='utf-8') as f:
            source_code = f.read()
    except Exception as e:
        print(f"Failed to read file: {e}")
        sys.exit(1)

    if not has_flask_or_jinja_import(source_code):
        print(f"Skipped: {os.path.basename(target_py_file)} does not import flask/jinja2.")
        sys.exit(0)

   
    try:
        ast_tree = ast.parse(source_code)
    except SyntaxError:
        print(f"Warning: {os.path.basename(target_py_file)} contains syntax errors. Proceeding with best-effort parsing.")
        ast_tree = None

    # AST Extraction & Jedi Inference
    final_render_contexts = []
    try:
        render_visitor = FlaskTemplateVisitor(source_code)
        ast_render_results = render_visitor.get_results()

        if ast_render_results:
            jedi_extractor = JediPropertyExtractor(source_code, max_depth=2)
            final_render_contexts = jedi_extractor.enrich_template_context(ast_render_results)
    except Exception as e:
        print(f"Context inference error: {e}")

    # Template Path Extraction 
    template_files = []
    if ast_tree:
        try:
            folder_extractor = TemplatePathExtractor(target_py_file)
            folder_extractor.visit(ast_tree)
            # Retrieves clean, relative Jinja paths (e.g., 'layouts/base.html')
            template_files = folder_extractor.get_template_files()
        except Exception as e:
            print(f"Template path extraction error: {e}")

    #  Custom Filter Extraction (For pipe '|' completion)
    custom_filters = []
    if ast_tree:
        try:
            filter_extractor = CustomFilterExtractor()
            filter_extractor.visit(ast_tree)
            custom_filters = filter_extractor.custom_filters
        except Exception as e:
            print(f"Filter extraction error: {e}")

    if not final_render_contexts and not template_files and not custom_filters:
        print(f"Skipped: {os.path.basename(target_py_file)} yielded no valuable template data.")
        sys.exit(0)

    # Assemble the comprehensive data contract expected by the TypeScript frontend
    comprehensive_data = {
        "source_file": target_py_file,
        "render_calls": final_render_contexts,  # Used for {{ variable.property }} completion
        "template_files": template_files,       # Used for {% extends "..." %} completion
        "custom_filters": custom_filters        # Used for {{ var | filter }} completion
    }

    # Ensure the output directory exists
    output_dir = os.path.join(workspace_root, "output_schemas")
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.basename(target_py_file)
    output_filepath = os.path.join(output_dir, f"{base_name}_schema.json")

    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(comprehensive_data, f, indent=4, ensure_ascii=False)
        print(f"Generated OmniJinja data contract: {output_filepath}")
    except Exception as e:
        print(f"Failed to write JSON schema: {e}")

if __name__ == "__main__":
    main()