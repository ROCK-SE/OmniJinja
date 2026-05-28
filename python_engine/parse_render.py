"""
OmniJinja Render Parser
-----------------------
Detects Python calls that render Jinja templates and extracts the context values
passed across the Python/Jinja boundary.
"""

import ast
from typing import Any, Dict, List

from render_context_tracker import LocalContextTracker


class FlaskTemplateVisitor(ast.NodeVisitor):
    """
    AST visitor for render_template(...), template.render(...), and simple
    project wrappers such as self.render("template.html", context).
    """

    def __init__(self, code: str):
        try:
            self.ast = ast.parse(code)
        except SyntaxError:
            self.ast = None

        self.global_context = {}
        self.current_function = None
        self.context_tracker = LocalContextTracker(self._prepare_for_jedi)
        self.render_calls = []

    def get_results(self) -> List[Dict[str, Any]]:
        if not self.ast:
            return []

        self.visit(self.ast)

        return [
            {
                "template": call["template"],
                "context": call["context"],
                "render_line": call["render_line"],
            }
            for call in self.render_calls
        ]

    def _prepare_for_jedi(self, node: ast.AST) -> dict:
        try:
            code_str = ast.unparse(node)
        except Exception:
            code_str = "<complex_expr>"

        schema_hint = self.context_tracker.schema_hint_for_node(node, self.current_function)

        return {
            "code": code_str,
            "line": getattr(node, "lineno", None),
            "column": getattr(node, "col_offset", None),
            "schema_hint": schema_hint or self.context_tracker.schema_hint_for_expr(code_str),
        }

    def is_render_call(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Name) and node.func.id == "render_template":
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr == "render":
            return True
        return False

    def _extract_template_name(self, node: ast.Call) -> str:
        for arg in node.args[:2]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return arg.value

        for keyword in node.keywords:
            if (
                keyword.arg in {"template", "template_name", "name"}
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            ):
                return keyword.value.value

        return "Unknown"

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._collect_context_processor_globals(node)

        previous_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = previous_function

    def _collect_context_processor_globals(self, node: ast.FunctionDef):
        for decorator in node.decorator_list:
            if (
                getattr(decorator, "attr", "") != "context_processor"
                and getattr(decorator, "id", "") != "context_processor"
            ):
                continue

            for stmt in node.body:
                if not isinstance(stmt, ast.Return) or not isinstance(stmt.value, ast.Dict):
                    continue

                for key, value in zip(stmt.value.keys, stmt.value.values):
                    if isinstance(key, ast.Constant):
                        self.global_context[key.value] = self._prepare_for_jedi(value)

    def visit_ClassDef(self, node: ast.ClassDef):
        self.context_tracker.track_class_definition(node)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            self.context_tracker.track_assignment(target, node.value, self.current_function)

        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if node.value:
            self.context_tracker.track_assignment(node.target, node.value, self.current_function)

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        self.context_tracker.track_call(node, self.current_function)

        if not self.is_render_call(node):
            self.generic_visit(node)
            return

        context_data = dict(self.global_context)
        template_name = self._extract_template_name(node)

        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                continue
            self.context_tracker.merge_context_payload(context_data, arg, self.current_function)

        for keyword in node.keywords:
            if keyword.arg:
                if keyword.arg in {"template", "template_name", "name"}:
                    continue
                if keyword.arg in {"context", "context_data"}:
                    before_count = len(context_data)
                    self.context_tracker.merge_context_payload(
                        context_data,
                        keyword.value,
                        self.current_function,
                    )
                    if len(context_data) != before_count:
                        continue
                context_data[keyword.arg] = self._prepare_for_jedi(keyword.value)
            else:
                self.context_tracker.merge_context_payload(
                    context_data,
                    keyword.value,
                    self.current_function,
                )

        self.render_calls.append({
            "template": template_name,
            "context": context_data,
            "render_line": getattr(node, "lineno", None),
        })

        self.generic_visit(node)
