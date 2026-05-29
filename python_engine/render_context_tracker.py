"""
Local render context tracker
----------------------------
Tracks simple local Python data-flow patterns that are commonly used to build
Jinja render context dictionaries.
"""

import ast
from collections import defaultdict
from typing import Callable


class LocalContextTracker:
    def __init__(self, prepare_for_jedi: Callable[[ast.AST], dict]):
        self.prepare_for_jedi = prepare_for_jedi
        self.dict_assignments = defaultdict(dict)
        self.list_schemas = defaultdict(dict)
        self.name_schemas = defaultdict(dict)
        self.model_schemas = {}
        self.schema_hints_by_expr = {}

    def generic_schema_leaf(self) -> dict:
        return {"__type__": "Any", "__is_iterable__": False}

    def schema_from_tracked_dict(self, dict_items: dict) -> dict:
        return {
            key: self.generic_schema_leaf()
            for key in dict_items.keys()
            if not str(key).startswith("__")
        }

    def schema_from_dict_node(self, node: ast.Dict) -> dict:
        return self.schema_from_tracked_dict({
            k.value: self.prepare_for_jedi(v)
            for k, v in zip(node.keys, node.values)
            if isinstance(k, ast.Constant)
        })

    def schema_from_list_elements(self, elements: list[ast.AST]) -> dict:
        element_schema = {}
        for element in elements:
            if isinstance(element, ast.Dict):
                self.merge_schema_children(element_schema, self.schema_from_dict_node(element))
        return element_schema

    def list_schema_from_element_schema(self, element_schema: dict) -> dict:
        return {
            "__type__": "List",
            "__is_iterable__": True,
            "__element__": element_schema or self.generic_schema_leaf(),
        }

    def merge_schema_children(self, target: dict, source: dict):
        for key, value in source.items():
            if key.startswith("__"):
                continue
            target[key] = value

    def schema_hint_for_node(self, node: ast.AST, current_function: str | None):
        if isinstance(node, ast.Name) and current_function:
            list_schema = self.list_schemas[current_function].get(node.id)
            if list_schema:
                return list_schema

            dict_items = self.dict_assignments[current_function].get(node.id)
            if dict_items:
                return {
                    "__type__": "Dictionary",
                    "__is_iterable__": True,
                    **self.schema_from_tracked_dict(dict_items),
                }

            name_schema = self.name_schemas[current_function].get(node.id)
            if name_schema:
                return name_schema

        if isinstance(node, ast.Dict):
            return {
                "__type__": "Dictionary",
                "__is_iterable__": True,
                **self.schema_from_dict_node(node),
            }

        if isinstance(node, ast.List):
            return self.list_schema_from_element_schema(self.schema_from_list_elements(node.elts))

        if isinstance(node, ast.ListComp) and isinstance(node.elt, ast.Dict):
            return self.list_schema_from_element_schema(self.schema_from_list_elements([node.elt]))

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            sqlalchemy_query_schema = self.schema_from_sqlalchemy_query_expr(node)
            if sqlalchemy_query_schema:
                return sqlalchemy_query_schema

            if node.func.attr in {"items", "lists", "keys", "values"}:
                return {
                    "__type__": "Iterable",
                    "__is_iterable__": True,
                    "__element__": self.generic_schema_leaf(),
                }

        sqlalchemy_query_schema = self.schema_from_sqlalchemy_query_expr(node)
        if sqlalchemy_query_schema:
            return sqlalchemy_query_schema

        return None

    def schema_hint_for_expr(self, expr: str):
        return self.schema_hints_by_expr.get(expr)

    def track_assignment(self, target: ast.AST, value: ast.AST, current_function: str | None):
        self._track_dict_literal_assignment(target, value, current_function)
        self._track_list_literal_assignment(target, value, current_function)
        self._track_dict_item_assignment(target, value, current_function)
        self._track_attribute_schema_assignment(target, value, current_function)
        self._track_name_schema_assignment(target, value, current_function)

    def track_class_definition(self, node: ast.ClassDef):
        if not self._is_sqlalchemy_model_class(node):
            return

        fields = {}
        for stmt in node.body:
            target_name = None
            value = None

            if isinstance(stmt, ast.Assign):
                value = stmt.value
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        target_name = target.id
                        break
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                target_name = stmt.target.id
                value = stmt.value

            if not target_name or value is None:
                continue

            field_schema = self._schema_from_sqlalchemy_column(value)
            if field_schema:
                fields[target_name] = field_schema

        if fields:
            self.model_schemas[node.name] = {
                "__type__": node.name,
                "__is_iterable__": False,
                **fields,
            }

    def track_call(self, node: ast.Call, current_function: str | None):
        self._track_list_append(node, current_function)
        self._track_dict_update(node, current_function)

    def merge_context_payload(self, context_data: dict, node: ast.AST, current_function: str | None):
        if isinstance(node, ast.Dict):
            self._merge_dict_literal(context_data, node)
        elif isinstance(node, ast.Name):
            self._merge_context_name(context_data, node, current_function)

    def _merge_dict_literal(self, context_data: dict, node: ast.Dict):
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant):
                context_data[k.value] = self.prepare_for_jedi(v)

    def _merge_context_name(self, context_data: dict, node: ast.Name, current_function: str | None) -> bool:
        if current_function and node.id in self.dict_assignments[current_function]:
            context_data.update(self.dict_assignments[current_function][node.id])
            return True
        return False

    def _get_constant_subscript_key(self, target: ast.AST):
        if not isinstance(target, ast.Subscript):
            return None
        if isinstance(target.slice, ast.Constant):
            return target.slice.value
        return None

    def _track_dict_literal_assignment(self, target: ast.AST, value: ast.AST, current_function: str | None):
        if not current_function or not isinstance(target, ast.Name) or not isinstance(value, ast.Dict):
            return

        dict_items = {}
        for k, v in zip(value.keys, value.values):
            if isinstance(k, ast.Constant):
                dict_items[k.value] = self.prepare_for_jedi(v)

        self.dict_assignments[current_function][target.id] = dict_items

    def _track_list_literal_assignment(self, target: ast.AST, value: ast.AST, current_function: str | None):
        if not current_function or not isinstance(target, ast.Name) or not isinstance(value, ast.List):
            return

        self.list_schemas[current_function][target.id] = self.list_schema_from_element_schema(
            self.schema_from_list_elements(value.elts)
        )

    def _track_name_schema_assignment(self, target: ast.AST, value: ast.AST, current_function: str | None):
        if not current_function or not isinstance(target, ast.Name):
            return

        schema_hint = self.schema_hint_for_node(value, current_function)
        if schema_hint:
            self.name_schemas[current_function][target.id] = schema_hint

    def _track_dict_item_assignment(self, target: ast.AST, value: ast.AST, current_function: str | None):
        if not current_function or not isinstance(target, ast.Subscript):
            return
        if not isinstance(target.value, ast.Name):
            return

        key = self._get_constant_subscript_key(target)
        if key is None:
            return

        dict_name = target.value.id
        self.dict_assignments[current_function].setdefault(dict_name, {})
        self.dict_assignments[current_function][dict_name][key] = self.prepare_for_jedi(value)

    def _track_attribute_schema_assignment(self, target: ast.AST, value: ast.AST, current_function: str | None):
        if not current_function or not isinstance(target, ast.Attribute):
            return
        if not isinstance(value, ast.Name):
            return

        local_list_schema = self.list_schemas[current_function].get(value.id)
        if not local_list_schema:
            return

        try:
            target_expr = ast.unparse(target)
        except Exception:
            return

        self.schema_hints_by_expr[target_expr] = local_list_schema

    def schema_from_sqlalchemy_query_expr(self, node: ast.AST):
        model_name = self._get_sqlalchemy_query_model_name(node)
        if not model_name:
            return None

        model_schema = self.model_schemas.get(model_name)
        if not model_schema:
            return None

        return {
            "__type__": "Query",
            "__is_iterable__": True,
            "__element__": dict(model_schema),
        }

    def _get_sqlalchemy_query_model_name(self, node: ast.AST):
        if isinstance(node, ast.Attribute) and node.attr == "query":
            if isinstance(node.value, ast.Name):
                return node.value.id
            return None

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"all", "filter", "filter_by", "order_by", "limit", "offset"}:
                return self._get_sqlalchemy_query_model_name(node.func.value)

        if isinstance(node, ast.Attribute):
            return self._get_sqlalchemy_query_model_name(node.value)

        return None

    def _is_sqlalchemy_model_class(self, node: ast.ClassDef) -> bool:
        for base in node.bases:
            if isinstance(base, ast.Attribute) and base.attr == "Model":
                return True
            if isinstance(base, ast.Name) and base.id == "Model":
                return True
        return False

    def _schema_from_sqlalchemy_column(self, node: ast.AST):
        if not isinstance(node, ast.Call):
            return None

        func = node.func
        if not (
            isinstance(func, ast.Attribute) and func.attr == "Column"
            or isinstance(func, ast.Name) and func.id == "Column"
        ):
            return None

        column_type = self._sqlalchemy_column_type_name(node)
        type_map = {
            "String": "String",
            "Text": "String",
            "Unicode": "String",
            "UnicodeText": "String",
            "Integer": "Integer",
            "SmallInteger": "Integer",
            "BigInteger": "Integer",
            "Float": "Float",
            "Numeric": "Float",
            "Boolean": "Boolean",
            "Date": "Date",
            "DateTime": "DateTime",
            "Time": "Time",
            "JSON": "Dictionary",
        }

        return {
            "__type__": type_map.get(column_type, column_type or "Any"),
            "__is_iterable__": False,
        }

    def _sqlalchemy_column_type_name(self, node: ast.Call):
        if not node.args:
            return None

        type_expr = node.args[0]
        if isinstance(type_expr, ast.Call):
            type_expr = type_expr.func

        if isinstance(type_expr, ast.Attribute):
            return type_expr.attr
        if isinstance(type_expr, ast.Name):
            return type_expr.id
        return None

    def _track_list_append(self, node: ast.Call, current_function: str | None):
        if not current_function:
            return
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "append":
            return
        if not isinstance(node.func.value, ast.Name) or not node.args:
            return

        list_name = node.func.value.id
        list_schema = self.list_schemas[current_function].setdefault(list_name, {
            "__type__": "List",
            "__is_iterable__": True,
            "__element__": {},
        })

        appended = node.args[0]
        if isinstance(appended, ast.Dict):
            self.merge_schema_children(
                list_schema["__element__"],
                self.schema_from_dict_node(appended),
            )
        elif isinstance(appended, ast.Name):
            dict_items = self.dict_assignments[current_function].get(appended.id)
            if dict_items:
                self.merge_schema_children(
                    list_schema["__element__"],
                    self.schema_from_tracked_dict(dict_items),
                )

    def _track_dict_update(self, node: ast.Call, current_function: str | None):
        if not current_function:
            return
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "update":
            return
        if not isinstance(node.func.value, ast.Name):
            return

        dict_name = node.func.value.id
        target_dict = self.dict_assignments[current_function].setdefault(dict_name, {})

        for arg in node.args:
            if isinstance(arg, ast.Dict):
                for k, v in zip(arg.keys, arg.values):
                    if isinstance(k, ast.Constant):
                        target_dict[k.value] = self.prepare_for_jedi(v)
            elif isinstance(arg, ast.Name):
                source_dict = self.dict_assignments[current_function].get(arg.id)
                if source_dict:
                    target_dict.update(source_dict)

        for keyword in node.keywords:
            if keyword.arg:
                target_dict[keyword.arg] = self.prepare_for_jedi(keyword.value)
