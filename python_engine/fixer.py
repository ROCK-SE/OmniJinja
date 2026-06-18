import re
from typing import List, Dict, Tuple
from error_models import SyntaxError


def process_extends_and_get_mapping(lines: List[str]) -> Tuple[List[str], Dict[int, int]]:
    """
    Process extends tag positions and generate original line number to new line number mapping.
    """
    line_mapping = {i+1: i+1 for i in range(len(lines))}
    extends_pattern = r'\{%\s*extends\s+.+?\s*%\}'
    
    extends_lines = [(idx, line) for idx, line in enumerate(lines) 
                    if re.match(extends_pattern, line.strip())]
    
    if not extends_lines:
        return lines.copy(), line_mapping
    
    first_extends_idx, first_extends_line = extends_lines[0]
    to_delete = [idx for idx, _ in extends_lines[1:]]
    
    insert_pos = 0
    while insert_pos < len(lines):
        current_line = lines[insert_pos].strip()
        if current_line and not (current_line.startswith('{#') and current_line.endswith('#}')):
            break
        insert_pos += 1
    
    new_lines = lines.copy()
    deleted_count = 0
    
    for del_idx in sorted(to_delete, reverse=True):
        del new_lines[del_idx]
        for orig_line in line_mapping:
            orig_idx = orig_line - 1
            if orig_idx > del_idx:
                line_mapping[orig_line] -= 1
        deleted_count += 1
    
    orig_first_extends_line = first_extends_idx + 1
    if first_extends_idx != insert_pos:
        del new_lines[first_extends_idx - deleted_count]
        new_lines.insert(insert_pos, first_extends_line)
        
        line_mapping[orig_first_extends_line] = insert_pos + 1
        for orig_line in line_mapping:
            orig_idx = orig_line - 1
            if insert_pos <= orig_idx < first_extends_idx:
                line_mapping[orig_line] += 1
    
    return new_lines, line_mapping


def find_insert_position_for_end_tag(lines: List[str], start_line_idx: int, start_indent: int) -> int:
    """
    Find the position where an end tag should be inserted for an unclosed tag.
    """
    for i in range(start_line_idx + 1, len(lines)):
        line = lines[i]
        if line.strip():
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= start_indent:
                insert_pos = i - 1
                while insert_pos > start_line_idx and not lines[insert_pos].strip():
                    insert_pos -= 1
                return insert_pos
    
    last_non_empty = len(lines) - 1
    while last_non_empty > start_line_idx and not lines[last_non_empty].strip():
        last_non_empty -= 1
    return last_non_empty


def replace_at_column(line: str, col: int, original: str, replacement: str) -> str:
    """
    Replace text at a 1-based diagnostic column. Falls back to the first occurrence
    only when the reported column no longer points at the expected text.
    """
    idx = max(col - 1, 0)
    if line[idx:idx + len(original)] == original:
        return line[:idx] + replacement + line[idx + len(original):]
    return line.replace(original, replacement, 1)


def fix_template(original_template: str, errors: List[SyntaxError]) -> str:
    """
    Generate a fixed template based on detected errors.
    """
    lines = original_template.split('\n')
    
    fixed_lines, line_mapping = process_extends_and_get_mapping(lines)
    
    corrected_errors = []
    for error in errors:
        if "Rule 4: Incorrect extends tag position" in error.rule:
            continue
        corrected_line = line_mapping.get(error.line, error.line)
        corrected_errors.append(SyntaxError(
            rule=error.rule,
            line=corrected_line,
            col=error.col,
            description=error.description,
            original=error.original,
            suggestion=error.suggestion
        ))
    
    errors_by_line: Dict[int, List[SyntaxError]] = {}
    for error in corrected_errors:
        if error.line not in errors_by_line:
            errors_by_line[error.line] = []
        errors_by_line[error.line].append(error)
    
    lines_to_delete = set()
    missing_end_tags_info = []
    
    for line_num in sorted(errors_by_line.keys(), reverse=True):
        line_idx = line_num - 1
        if line_idx >= len(fixed_lines):
            continue
        
        line = fixed_lines[line_idx]
        
        # Process "Malformed opening" fixes first so that lone-{ → {%
        # repairs happen before we decide whether an end-tag is "extra".
        for error in sorted(errors_by_line[line_num],
                            key=lambda e: (0 if 'Malformed' in e.description else 1,
                                           -e.col)):
            # Fix Rule 1: Nested delimiters
            if "Rule 1" in error.rule:
                match = re.search(r'\{\{\s*([^}]+?)\s*\}\}', error.original)
                if match:
                    var_content = match.group(1).strip()
                    line = line.replace(error.original, var_content, 1)
            
            # Fix Rule 3: Property access
            elif "Rule 3" in error.rule:
                if '->' in error.original:
                    fixed_access = error.original.replace('->', '.')
                    line = line.replace(error.original, fixed_access, 1)
                elif '..' in error.original and not error.original.endswith('.'):
                    fixed_access = error.original.replace('..', '.')
                    line = line.replace(error.original, fixed_access, 1)
                elif error.original.endswith('.'):
                    fixed_access = error.original.rstrip('.')
                    line = line.replace(error.original, fixed_access, 1)
            
            # Fix Rule 2: Delimiter syntax
            elif "Rule 2" in error.rule:
                # Handle malformed opening delimiter: lone { should be {%
                if "Malformed opening" in error.description:
                    old_len = len(line)
                    line = replace_at_column(line, error.col, error.original, '{%')
                    # The line grew by 1 char ({ → {%); shift columns of
                    # remaining errors on this line that are past the fix.
                    shift = len(line) - old_len
                    if shift:
                        for later_err in errors_by_line[line_num]:
                            if later_err.col > error.col:
                                later_err.col += shift

                # Handle extra closing tags/delimiters
                elif "extra closing" in error.description.lower():
                    # If an earlier "Malformed opening" fix on this line
                    # has created a matching opener, this closer is no
                    # longer extra — skip removal.
                    if error.original.startswith('{%'):
                        tag_m = re.match(r'\{%-?\s*(\w+)', error.original)
                        if tag_m:
                            closer_name = tag_m.group(1)
                            if closer_name.startswith('end'):
                                opener_name = closer_name[3:]
                                if re.search(r'\{%-?\s*\b' + opener_name + r'\b', line):
                                    continue  # now properly paired

                    col_idx = error.col - 1
                    # For tags ({%...%}), remove the whole block including the closing %}
                    if error.original.startswith('{%'):
                        close_pos = line.find('%}', col_idx)
                        if close_pos != -1:
                            line = line[:col_idx] + line[close_pos + 2:]
                        else:
                            line = line.replace(error.original, '', 1)
                    # For outputs ({{...}}), remove the whole block including closing }}
                    elif error.original.startswith('{{'):
                        close_pos = line.find('}}', col_idx)
                        if close_pos != -1:
                            line = line[:col_idx] + line[close_pos + 2:]
                        else:
                            line = line.replace(error.original, '', 1)
                    else:
                        # Pure delimiter extra (like stray %}, }}, #})
                        line = replace_at_column(line, error.col, error.original, '').rstrip()
                
                # Handle mismatched delimiters/tags
                elif "mismatch" in error.description.lower():
                    if "Change" in error.suggestion:
                        match = re.search(r'Change .+ to (\S+)$', error.suggestion)
                        if match:
                            correct_str = match.group(1)
                            col_idx = error.col - 1
                            # For tag mismatches (e.g. {% endfor %} should be {% endif %})
                            # replace the whole tag block, not just the incomplete prefix
                            if error.original.startswith('{%'):
                                close_pos = line.find('%}', col_idx)
                                if close_pos != -1:
                                    line = line[:col_idx] + '{% ' + correct_str + ' %}' + line[close_pos + 2:]
                                else:
                                    line = replace_at_column(line, error.col, error.original, '{% ' + correct_str + ' %}')
                            elif error.original.startswith('{{'):
                                close_pos = line.find('}}', col_idx)
                                if close_pos != -1:
                                    line = line[:col_idx] + '{{ ' + correct_str + ' }}' + line[close_pos + 2:]
                                else:
                                    line = replace_at_column(line, error.col, error.original, correct_str)
                            else:
                                # Pure delimiter mismatch (e.g. %} → }})
                                line = replace_at_column(line, error.col, error.original, correct_str)
                
                # Handle unclosed tags/delimiters
                elif "Unclosed" in error.description:
                    stripped_line = line.rstrip()
                    
                    # 1. Handle Unclosed Comments {#
                    if "{#" in error.original:
                        if stripped_line.endswith('}'):
                            # Replace trailing lone } with proper #} close
                            line = stripped_line[:-1] + '#}'
                        elif stripped_line.endswith('#'):
                            line = stripped_line + '}'
                        else:
                            line = stripped_line + ' #}'
                    
                    # 2. Handle Unclosed Variables {{
                    elif "{{" in error.original:
                        # Check if it partially closes with }
                        if stripped_line.endswith('}'):
                            line = stripped_line + "}"
                        else:
                            line = stripped_line + " }}"
                    
                    # 3. Handle Statements {%
                    elif "{%" in error.original:

                        # Check whether the tag's own %} is present on this line
                        # (search from the {% opening position onwards)
                        tag_close_pos = stripped_line.find('%}', error.col - 1)

                        # CASE A: The tag delimiter itself is missing (e.g., "{% set x", "{% if x")
                        if tag_close_pos == -1:
                            if stripped_line.endswith('}'):
                                # Replace trailing lone } with proper %} close
                                line = stripped_line[:-1] + '%}'
                            elif stripped_line.endswith('%'):
                                line = stripped_line + '}'
                            else:
                                line = stripped_line + ' %}'
                        
                        # CASE B: The tag is closed, but it's a block opener missing its closer
                        else:
                            original_line = fixed_lines[error.line - 1]
                            indent = len(original_line) - len(original_line.lstrip())
                            indent_str = original_line[:indent]

                            # Extract the tag name from original (e.g. "{% if" → "if", "{%comment" → "comment")
                            tag_match = re.match(r'\{%-?\s*(\w+)', error.original)
                            tag_name = tag_match.group(1) if tag_match else None

                            # Map opener tag names to their corresponding end-tag templates
                            _END_TAG_MAP = {
                                'if': '{% endif %}',
                                'for': '{% endfor %}',
                                'with': '{% endwith %}',
                                'block': '{% endblock %}',
                                'macro': '{% endmacro %}',
                                'call': '{% endcall %}',
                                'autoescape': '{% endautoescape %}',
                                'filter': '{% endfilter %}',
                                'comment': '{% endcomment %}',
                                'raw': '{% endraw %}',
                            }

                            end_tag = None
                            if tag_name and tag_name in _END_TAG_MAP:
                                end_tag = f"{indent_str}{_END_TAG_MAP[tag_name]}"

                            if end_tag:
                                # Only add a closing tag when the template has
                                # more openers than closers for this tag type
                                # (handles nesting and lone-{ fixes correctly).
                                tag_re = re.compile(r'\{%-?\s*(\w+)')
                                opener_cnt = 0
                                closer_cnt = 0
                                for i, fl in enumerate(fixed_lines):
                                    # Use the in-progress line for the row we are
                                    # fixing (earlier error fixes on this row may
                                    # have already added the closer).
                                    l = line if i == line_idx else fl
                                    for m in tag_re.finditer(l):
                                        n = m.group(1)
                                        if n == tag_name:
                                            opener_cnt += 1
                                        elif n == 'end' + tag_name:
                                            closer_cnt += 1
                                if opener_cnt > closer_cnt:
                                    insert_line = find_insert_position_for_end_tag(
                                        fixed_lines, error.line - 1, indent
                                    )
                                    missing_end_tags_info.append((end_tag, insert_line, error.line))
        
        fixed_lines[line_idx] = line
    
    for line_idx in sorted(lines_to_delete, reverse=True):
        del fixed_lines[line_idx]
    
    missing_end_tags_info.sort(key=lambda x: x[1], reverse=True)
    for end_tag, insert_line, start_line in missing_end_tags_info:
        adjusted_insert_line = insert_line
        for deleted_idx in lines_to_delete:
            if deleted_idx < insert_line:
                adjusted_insert_line -= 1
        
        if adjusted_insert_line < len(fixed_lines):
            fixed_lines.insert(adjusted_insert_line + 1, end_tag)
        else:
            fixed_lines.append(end_tag)
    
    result_lines = []
    empty_count = 0
    for line in fixed_lines:
        is_empty = not line.strip()
        if is_empty:
            empty_count += 1
            if empty_count <= 1:
                result_lines.append(line)
        else:
            empty_count = 0
            result_lines.append(line)
    
    while result_lines and not result_lines[-1].strip():
        result_lines.pop()
    
    return '\n'.join(result_lines)
