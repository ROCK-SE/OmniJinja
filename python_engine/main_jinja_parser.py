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
from jinja2 import Environment, nodes
from block_complete import JinjaBlockExtractor
from marco_complete import JinjaMacroExtractor
from extract_internal_symbols import JinjaSymbolExtractor
from template_semantic_linter import JinjaSemanticLinter
from detector import analyze_template
from fixer import fix_template
from extract_external_symbols import extract_external_requirements

def _normalize_template_name(template_name):
    return template_name.replace('\\', '/')

def _template_name_aliases(template_name):
    normalized = _normalize_template_name(template_name)
    aliases = {normalized}
    basename = os.path.basename(normalized)
    if basename:
        aliases.add(basename)
    return aliases

def _merge_dict(target, source):
    for key, value in source.items():
        target[key] = value
    return target

def get_merged_backend_schema(output_schemas_dir, target_template_names):
    merged_schema = {}
    custom_filters = set()
    if isinstance(target_template_names, str):
        target_template_names = [target_template_names]
    target_template_names = {
        alias
        for name in target_template_names
        if name
        for alias in _template_name_aliases(name)
    }

    if not os.path.exists(output_schemas_dir):
        return merged_schema, custom_filters

    for filename in os.listdir(output_schemas_dir):
        if filename.endswith("_schema.json") and not filename.endswith("_jinja.json"):
            filepath = os.path.join(output_schemas_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    if "render_calls" in data:
                        for call in data["render_calls"]:
                            call_template_names = _template_name_aliases(call.get("template", ""))
                            if call_template_names.intersection(target_template_names):
                                _merge_dict(merged_schema, call.get("context", {}))

                    if "custom_filters" in data:
                        for cf in data["custom_filters"]:
                            custom_filters.add(cf.get("name"))
            except Exception:
                pass

    return merged_schema, custom_filters

def _template_key_from_path(template_path):
    normalized_path = _normalize_template_name(template_path)
    if "/templates/" in normalized_path:
        return normalized_path.split("/templates/")[-1]
    return os.path.basename(template_path)

def _templates_root_from_path(template_path):
    normalized_path = _normalize_template_name(template_path)
    marker = "/templates/"
    if marker in normalized_path:
        return normalized_path.split(marker)[0] + marker[:-1]
    return os.path.dirname(template_path)

def _resolve_template_path(template_name, current_template_path, workspace_root):
    candidates = []
    template_name = _normalize_template_name(template_name)

    if os.path.isabs(template_name):
        candidates.append(template_name)
    else:
        current_dir = os.path.dirname(current_template_path)
        templates_root = _templates_root_from_path(current_template_path)
        candidates.append(os.path.join(templates_root, template_name))
        candidates.append(os.path.join(current_dir, template_name))
        candidates.append(os.path.join(workspace_root, template_name))

    for candidate in candidates:
        if os.path.exists(candidate) and os.path.isfile(candidate):
            return candidate
    return None

def _extract_const_extends(template_code):
    try:
        ast_tree = Environment().parse(template_code)
    except Exception:
        return None
    try:
        extends_node = next(ast_tree.find_all(nodes.Extends), None)
        if extends_node and isinstance(extends_node.template, nodes.Const):
            return extends_node.template.value
    except Exception:
        return None
    return None

def collect_parent_template_names(template_code, template_path, workspace_root):
    parents = []
    for parent in collect_parent_templates(template_code, template_path, workspace_root):
        parents.append(parent["name"])
    return parents

def collect_parent_templates(template_code, template_path, workspace_root):
    parents = []
    visited = set()
    current_code = template_code
    current_path = template_path

    while True:
        parent_name = _extract_const_extends(current_code)
        if not parent_name or parent_name in visited:
            break
        visited.add(parent_name)

        parent_path = _resolve_template_path(parent_name, current_path, workspace_root)
        if not parent_path:
            parents.append({
                "name": _normalize_template_name(parent_name),
                "path": None,
                "code": ""
            })
            break
        try:
            with open(parent_path, "r", encoding="utf-8") as f:
                parent_code = f.read()
            parents.append({
                "name": _normalize_template_name(parent_name),
                "path": parent_path,
                "code": parent_code
            })
            current_code = parent_code
            current_path = parent_path
        except Exception:
            break

    return parents

def get_template_internal_exports(template_code, backend_schema):
    exports = {}
    if not template_code:
        return exports

    internal_vars = JinjaSymbolExtractor(backend_schema).extract(template_code)
    _merge_dict(exports, internal_vars.get("globals", {}))

    macros = JinjaMacroExtractor().extract_macros(template_code)
    _merge_dict(exports, macros)
    return exports

def _requirement_satisfied(requirement_node, schema_node):
    if schema_node is None:
        return False
    if not isinstance(requirement_node, dict) or not isinstance(schema_node, dict):
        return True

    if requirement_node.get("__is_callable__"):
        schema_type = schema_node.get("__type__")
        if schema_type and schema_type not in {"Function", "Method", "Macro", "Any"}:
            return False

    if requirement_node.get("__is_iterable__"):
        schema_type = schema_node.get("__type__")
        is_iterable = schema_node.get("__is_iterable__") or schema_type in {"Iterable", "List", "Tuple", "Dict", "Any"}
        if not is_iterable:
            return False

    child_keys = [key for key in requirement_node.keys() if not key.startswith("__")]
    if not child_keys:
        return True
    if _is_generic_schema_leaf(schema_node):
        return True

    for key in child_keys:
        if key not in schema_node:
            return False
        if not _requirement_satisfied(requirement_node[key], schema_node[key]):
            return False
    return True

def _has_known_schema_children(schema_node):
    if not isinstance(schema_node, dict):
        return False
    metadata_keys = {"def_line", "args", "signature", "docstring"}
    return any(not key.startswith("__") and key not in metadata_keys for key in schema_node.keys())

def _is_generic_schema_leaf(schema_node):
    return isinstance(schema_node, dict) and "__type__" in schema_node and not _has_known_schema_children(schema_node)

def prune_requirements_satisfied_by_schema(requirements, inherited_schema):
    if not isinstance(requirements, dict) or not isinstance(inherited_schema, dict):
        return requirements

    pruned = {}
    for key, requirement in requirements.items():
        if key.startswith("__"):
            pruned[key] = requirement
            continue

        schema_node = inherited_schema.get(key)
        if _requirement_satisfied(requirement, schema_node):
            continue

        if isinstance(requirement, dict) and isinstance(schema_node, dict):
            nested = prune_requirements_satisfied_by_schema(requirement, schema_node)
            if nested:
                pruned[key] = nested
        else:
            pruned[key] = requirement

    return pruned

def main():
    """
    Orchestrates the full analysis pipeline for a specific Jinja2 template.

    Execution Flow:
    1. Setup directories and load merged backend context.
    2. Extract metadata (inheritance blocks, macros, internal symbols).
    3. Perform semantic checks (undefined variables -> Warnings).
    4. Perform structural checks (syntax rules -> Errors/Warnings) and calculate repairs.
    5. Export consolidated results to a JSON file.
    """
    if len(sys.argv) < 4:
        print("Usage: python main_jinja_parser.py <template_path> <workspace_root> <storage_path>")
        return

    template_path = sys.argv[1]
    workspace_root = sys.argv[2]
    storage_path = sys.argv[3]

    output_schemas_dir = os.path.join(storage_path, "backend_schemas")
    jinja_schemas_dir = os.path.join(storage_path, "jinja_schemas")

    template_code = sys.stdin.read()
    code_lines = template_code.splitlines()

    target_template_name = _template_key_from_path(template_path)
    parent_templates = collect_parent_templates(template_code, template_path, workspace_root)
    parent_template_names = [parent["name"] for parent in parent_templates]

    own_backend_schema, custom_filters = get_merged_backend_schema(output_schemas_dir, target_template_name)
    inherited_backend_schema, inherited_filters = get_merged_backend_schema(output_schemas_dir, parent_template_names)
    custom_filters.update(inherited_filters)

    backend_schema = {}
    _merge_dict(backend_schema, inherited_backend_schema)
    _merge_dict(backend_schema, own_backend_schema)

    inherited_template_exports = {}
    for parent in reversed(parent_templates):
        parent_exports = get_template_internal_exports(parent.get("code", ""), backend_schema)
        _merge_dict(inherited_template_exports, parent_exports)
        _merge_dict(backend_schema, parent_exports)

    template_dir = os.path.dirname(template_path)


    def is_ignored(line_number):
        idx = line_number - 1
        if idx < 0 or idx >= len(code_lines):
            return False

        ignore_tag = "{# omnijinja-ignore #}"
        if ignore_tag in code_lines[idx]:
            return True
        if idx > 0 and ignore_tag in code_lines[idx - 1]:
            return True
        return False

    # 1. Metadata Extraction
    block_extractor = JinjaBlockExtractor(template_dir)
    blocks = block_extractor.get_inherited_blocks(template_code)

    macro_extractor = JinjaMacroExtractor()
    macros = macro_extractor.extract_macros(template_code)

    symbol_extractor = JinjaSymbolExtractor(backend_schema)
    internal_vars = symbol_extractor.extract(template_code)
    external_reqs = prune_requirements_satisfied_by_schema(
        extract_external_requirements(template_code),
        {**inherited_backend_schema, **inherited_template_exports}
    )

    # 2. Diagnostic Generation
    # Undefined - Warnings
    linter = JinjaSemanticLinter(backend_schema, custom_filters)
    raw_undefined_diagnostics = linter.lint(template_code)
    diagnostics = [d for d in raw_undefined_diagnostics if not is_ignored(d.get('line', 0))]

    # Syntax Errors - Errors + Fixes
    all_syntax_issues = analyze_template(template_code)
    fixed_code = None

    if all_syntax_issues:

        fixable_errors = [err for err in all_syntax_issues if "Rule 5" not in err.rule]

        if fixable_errors:
            try:
                fixed_code = fix_template(template_code, fixable_errors)
            except Exception:
                pass

        for err in all_syntax_issues:
            if is_ignored(err.line):
                continue

            is_warning = "Rule 5" in err.rule
            severity_level = "warning" if is_warning else "error"

            icon = "⚠️" if is_warning else "🚨"

            formatted_message = (
                f"{icon} [{err.rule}]\n\n"
                f"🔍 Reason:\n{err.description}\n\n"
                f"💡 Advice:\n{err.suggestion}"
            )

            diagnostics.append({
                "line": err.line,
                "col": err.col,
                "message": formatted_message,
                "original": err.original,
                "severity": severity_level
            })

    result = {
        "blocks": blocks,
        "macros": macros,
        "internal_variables": internal_vars,
        "external_requirements": external_reqs,
        "diagnostics": diagnostics,
        "fixed_code": fixed_code
    }

    try:
        rel_path = os.path.relpath(template_path, workspace_root)
        safe_name = rel_path.replace(os.sep, '_').replace('/', '_')
    except Exception:
        safe_name = os.path.basename(template_path)

    output_filename = os.path.join(jinja_schemas_dir, f"{safe_name}_jinja.json")

    os.makedirs(jinja_schemas_dir, exist_ok=True)
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    main()
