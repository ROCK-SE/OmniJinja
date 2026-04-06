"""
OmniJinja Backend Orchestrator
-----------------------------
This module serves as the primary integration layer between the VS Code extension 
and the Python-based Jinja2 analysis suite. It coordinates variable extraction, 
inheritance tracing, macro analysis, and structural syntax validation.

The script aggregates data from various specialized modules and produces a 
unified JSON payload consumed by the TypeScript frontend.
"""
import sys
import os
import json
from pathlib import Path
from block_complete import JinjaBlockExtractor
from marco_complete import JinjaMacroExtractor
from extract_internal_symbols import JinjaSymbolExtractor
from variable_undefined import JinjaUndefinedLinter
from detector import analyze_template
from fixer import fix_template

def get_merged_backend_schema(output_schemas_dir):
    merged_schema = {}
    if not os.path.exists(output_schemas_dir):
        return merged_schema
        
    for filename in os.listdir(output_schemas_dir):
        if filename.endswith("_schema.json") and not filename.endswith("_jinja.json"):
            filepath = os.path.join(output_schemas_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "render_calls" in data:
                        for call in data["render_calls"]:
                            merged_schema.update(call.get("context", {}))
            except Exception:
                pass
    return merged_schema

def main():
    """
    Orchestrates the full analysis pipeline for a specific Jinja2 template.
    
    Execution Flow:
    1. Setup directories and load merged backend context.
    2. Extract metadata (inheritance blocks, macros, internal symbols).
    3. Perform semantic checks (undefined variables -> Warnings).
    4. Perform structural checks (syntax rules -> Errors) and calculate repairs.
    5. Export consolidated results to a JSON file.
    """
    if len(sys.argv) < 3:
        print("Usage: python jinja_main_parser.py <template_path> <workspace_root>")
        return

    template_path = sys.argv[1]
    workspace_root = sys.argv[2]
    output_schemas_dir = os.path.join(workspace_root, "output_schemas")
    jinja_schemas_dir = os.path.join(workspace_root, "jinja_schemas")
    
    backend_schema = get_merged_backend_schema(output_schemas_dir)
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template_code = f.read()
        
    template_dir = os.path.dirname(template_path)

    # 1. Metadata Extraction
    block_extractor = JinjaBlockExtractor(template_dir)
    blocks = block_extractor.get_inherited_blocks(template_code)
    
    macro_extractor = JinjaMacroExtractor()
    macros = macro_extractor.extract_macros(template_code)
    
    symbol_extractor = JinjaSymbolExtractor(backend_schema)
    internal_vars = symbol_extractor.extract(template_code)
    
    # 2. Diagnostic Generation
    # Undefined - Warnings
    linter = JinjaUndefinedLinter(backend_schema)
    diagnostics = linter.lint(template_code)

    # Syntax Errors - Errors + Fixes
    syntax_errors = analyze_template(template_code)
    fixed_code = None
    
    if syntax_errors:
        fixed_code = fix_template(template_code, syntax_errors)
        
        for err in syntax_errors:
            diagnostics.append({
                "line": err.line,
                "col": err.col, 
                "message": f"[{err.rule}]\nReason: {err.description}\nAdvice: {err.suggestion}",
                "original": err.original,
                "severity": "error" 
            })

    result = {
        "blocks": blocks,
        "macros": macros,
        "internal_variables": internal_vars,
        "diagnostics": diagnostics,
        "fixed_code": fixed_code 
    }
    
    base_name = os.path.basename(template_path)
    output_filename = os.path.join(jinja_schemas_dir, f"{base_name}_jinja.json")
    
    os.makedirs(jinja_schemas_dir, exist_ok=True)
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    main()