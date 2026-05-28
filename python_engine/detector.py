"""
OmniJinja Static Syntax Detector
-------------------------------
This module implements rule-based static analysis for Jinja2 templates.
It detects common syntax pitfalls that the standard Jinja2 parser might
ignore or throw cryptic errors for.
"""

import re
from typing import List
from error_models import SyntaxError, State


RAW_TAG_PATTERN = re.compile(r'\{%-?\s*(raw|endraw)\b.*?-?%\}', re.DOTALL)


def mask_raw_blocks(template: str) -> str:
    """
    Keep raw/endraw tags visible, but hide the literal body from lightweight
    regex checks while preserving line and column positions.
    """
    chars = list(template)
    raw_body_start = None

    for match in RAW_TAG_PATTERN.finditer(template):
        tag_name = match.group(1)
        if tag_name == "raw" and raw_body_start is None:
            raw_body_start = match.end()
            continue

        if tag_name == "endraw" and raw_body_start is not None:
            for idx in range(raw_body_start, match.start()):
                if chars[idx] != "\n":
                    chars[idx] = " "
            raw_body_start = None

    if raw_body_start is not None:
        for idx in range(raw_body_start, len(chars)):
            if chars[idx] != "\n":
                chars[idx] = " "

    return "".join(chars)


def check_nested_delimiters(template: str) -> List[SyntaxError]:
    """
    Check for nested {{ }} inside {{ }} or {% %}.
    Targeted Detections:
    1. {{ ... }} inside {% ... %} (Redundant braces -> Fixable)
    2. {{ ... }} inside {{ ... }} (Redundant braces -> Fixable)
    """
    errors = []
    state = State.NORMAL
    line_num = 1
    col = 1
    i = 0

    while i < len(template):
        char = template[i]
        
        # Track line and column numbers
        if char == '\n':
            line_num += 1
            col = 1
            i += 1
            continue
        
        # Check for two-character delimiters
        if i + 1 < len(template):
            two_char = template[i:i+2]
            
            # Transition from NORMAL state when encountering opening delimiters
            if state == State.NORMAL:
                if two_char in ('{%', '{{', '{#'):
                    state = {
                        '{%': State.IN_TAG,
                        '{{': State.IN_OUTPUT,
                        '{#': State.IN_COMMENT
                    }[two_char]
                    i += 2
                    col += 2
                    continue

            elif state == State.IN_TAG:
                # 1. DETECT: Nested {{ inside {% (Fixable)
                if two_char == '{{':
                    nested_end = _find_closing(template, i, '{{', '}}')
                    if nested_end != -1:
                        nested_str = template[i:nested_end+2]
                        nested_content = template[i+2:nested_end].strip()
                        
                        errors.append(SyntaxError(
                            rule="Rule 1: Nested {{ }} inside {% %} or {{ }}",
                            line=line_num,
                            col=col,
                            description=f"{{ {{{{ }}}} }} is not allowed inside {{% %}} tags",
                            original=nested_str,
                            suggestion=f"Use directly: {nested_content}"
                        ))
                        
                        jump_len = (nested_end + 2) - i
                        
                        skipped_text = template[i:i+jump_len]
                        newlines = skipped_text.count('\n')
                        line_num += newlines
                        if newlines > 0:
                            last_newline_idx = skipped_text.rfind('\n')
                            col = len(skipped_text) - last_newline_idx
                        else:
                            col += jump_len
                            
                        i += jump_len
                        continue
                    else:
                        i += 2
                        col += 2
                        continue
                
                elif two_char == '%}':
                    state = State.NORMAL
                    i += 2
                    col += 2
                    continue
                
                elif two_char in ('}}', '#}'):
                    state = State.NORMAL
                    i += 2
                    col += 2
                    continue

            elif state == State.IN_OUTPUT:
                # 1. DETECT: Nested {{ inside {{ (Fixable)
                if two_char == '{{':
                    nested_end = _find_closing(template, i, '{{', '}}')
                    if nested_end != -1:
                        nested_str = template[i:nested_end+2]
                        nested_content = template[i+2:nested_end].strip()
                        
                        errors.append(SyntaxError(
                            rule="Rule 1: Nested {{ }} inside {% %} or {{ }}",
                            line=line_num,
                            col=col,
                            description=f"Nested {{ {{{{ }}}} }} is not allowed inside {{{{ }}}} output blocks",
                            original=nested_str,
                            suggestion=f"Use directly: {nested_content}"
                        ))
                        
                        jump_len = (nested_end + 2) - i
                        
                        skipped_text = template[i:i+jump_len]
                        newlines = skipped_text.count('\n')
                        line_num += newlines
                        if newlines > 0:
                            last_newline_idx = skipped_text.rfind('\n')
                            col = len(skipped_text) - last_newline_idx
                        else:
                            col += jump_len
                            
                        i += jump_len
                        continue
                    else:
                        i += 2
                        col += 2
                        continue

                elif two_char == '}}':
                    state = State.NORMAL
                    i += 2
                    col += 2
                    continue

                elif two_char in ('%}', '#}'):
                    state = State.NORMAL
                    i += 2
                    col += 2
                    continue
            
            elif state == State.IN_COMMENT:
                if two_char == '#}':
                    state = State.NORMAL
                    i += 2
                    col += 2
                    continue
                
                elif two_char in ('%}', '}}'):
                    state = State.NORMAL
                    i += 2
                    col += 2
                    continue
        
        i += 1
        col += 1
    return errors


def check_delimiter_mismatch(template: str) -> List[SyntaxError]:
    """
    Check if delimiters are properly paired and closed.
    """
    errors = []
    delimiters = []
    i = 0
    line_num = 1
    col = 1

    while i < len(template):
        if template[i] == '\n':
            line_num += 1
            col = 1
            i += 1
            continue
        
        if i + 1 < len(template):
            two_char = template[i:i+2]
            delim_info = {
                '{%': ('open', 'tag'),
                '{{': ('open', 'output'),
                '{#': ('open', 'comment'),
                '%}': ('close', 'tag'),
                '}}': ('close', 'output'),
                '#}': ('close', 'comment')
            }.get(two_char)
            
            if delim_info:
                delim_type, delim_subtype = delim_info
                delimiters.append((delim_type, delim_subtype, line_num, col, two_char))
                i += 2
                col += 2
                continue
        
        i += 1
        col += 1

    stack = []
    for delim_type, delim_subtype, line, col, delim_str in delimiters:
        if delim_type == 'open':
            stack.append((delim_subtype, line, col, delim_str))
        else:
            if not stack:
                errors.append(SyntaxError(
                    rule="Rule 2: Delimiter syntax error",
                    line=line,
                    col=col,
                    description=f"Found extra closing delimiter {delim_str}",
                    original=delim_str,
                    suggestion=f"Check if there is redundant {delim_str}"
                ))
            elif stack[-1][0] != delim_subtype:
                expected_close = _get_closing_delimiter(stack[-1][0])
                errors.append(SyntaxError(
                    rule="Rule 2: Delimiter syntax error",
                    line=line,
                    col=col,
                    description=f"Delimiter mismatch. {stack[-1][3]} expects to be closed by {expected_close}, but found {delim_str}",
                    original=delim_str,
                    suggestion=f"Change {delim_str} to {expected_close}"
                ))
                stack.pop()
            else:
                stack.pop()

    for delim_subtype, line, col, delim_str in stack:
        closing = _get_closing_delimiter(delim_subtype)
        errors.append(SyntaxError(
            rule="Rule 2: Delimiter syntax error",
            line=line,
            col=col,
            description=f"Unclosed delimiter {delim_str}, missing {closing}",
            original=delim_str,
            suggestion=f"Add closing delimiter {closing}"
        ))
    return errors


def check_tag_logic_pairing(lines: List[str]) -> List[SyntaxError]:
    """
    Check logical pairing of block tags like if/endif, for/endfor.
    """
    errors = []
    stack = []
    start_tags = {
        'if': 'endif',
        'for': 'endfor',
        'block': 'endblock',
        'macro': 'endmacro',
        'call': 'endcall',
        'with': 'endwith',
        'autoescape': 'endautoescape',
        'filter': 'endfilter',
        'raw': 'endraw'
    }
    
    tag_pattern = r'\{%\s*(\w+)'

    for line_num, line in enumerate(lines, 1):
        for match in re.finditer(tag_pattern, line):
            tag_name = match.group(1)
            col = match.start() + 1
            full_tag = match.group(0) 
            
            if tag_name in start_tags:
                stack.append((tag_name, line_num, col, full_tag))
            elif tag_name.startswith('end'):
                end_tag_name = tag_name[3:]
                
                if not stack:
                    errors.append(SyntaxError(
                        rule="Rule 2: Delimiter syntax error",
                        line=line_num,
                        col=col,
                        description=f"Found extra closing tag {tag_name} without corresponding opening tag",
                        original=full_tag,
                        suggestion=f"Check if there is redundant {tag_name}"
                    ))
                elif stack[-1][0] != end_tag_name:
                    expected_end = f"end{stack[-1][0]}"
                    errors.append(SyntaxError(
                        rule="Rule 2: Delimiter syntax error",
                        line=line_num,
                        col=col,
                        description=f"Tag mismatch. {stack[-1][3]} expects to be closed by {expected_end}, but found {tag_name}",
                        original=full_tag,
                        suggestion=f"Change {tag_name} to {expected_end}"
                    ))
                    stack.pop()
                else:
                    stack.pop()

    for tag_name, line, col, full_tag in stack:
        end_tag = f"end{tag_name}"
        errors.append(SyntaxError(
            rule="Rule 2: Delimiter syntax error",
            line=line,
            col=col,
            description=f"Unclosed tag {full_tag}, missing {end_tag}",
            original=full_tag,
            suggestion=f"Add closing tag {{% {end_tag} %}}"
        ))
    return errors


def check_property_access(lines: List[str]) -> List[SyntaxError]:
    """
    Check if variable property access syntax is correct.
    """
    errors = []
    # Pattern to extract content inside tags
    tag_pattern = r'\{%\s*([^%]*?)\s*%\}|\{\{\s*([^}]*?)\s*\}\}'

    for line_num, line in enumerate(lines, 1):
        for match in re.finditer(tag_pattern, line):
            content = match.group(1) if match.group(1) is not None else match.group(2)
            errors.extend(_check_invalid_property_access(content, line_num, match.start() + 1))
    return errors


def check_extends_position(lines: List[str]) -> List[SyntaxError]:
    """
    Check if extends tag is at the absolute first valid position.
    """
    errors = []
    extends_pattern = r'\{%\s*extends\s+(.+?)\s*%\}'
    extends_lines = []
    valid_lines = []

    for line_num, line in enumerate(lines, 1):
        stripped_line = line.strip()
        if not stripped_line:
            continue
        if stripped_line.startswith('{#') and stripped_line.endswith('#}'):
            continue
        
        valid_lines.append((line_num, line))
        if re.match(extends_pattern, stripped_line):
            extends_lines.append((line_num, line, stripped_line))

    if extends_lines:
        first_extends_line_num, _, first_extends_stripped = extends_lines[0]
        if valid_lines:
            first_valid_line_num, _ = valid_lines[0]
            if first_valid_line_num != first_extends_line_num:
                col = line.find('{% extends') + 1 if '{% extends' in line else 1
                errors.append(SyntaxError(
                    rule="Rule 4: extends tag must be the absolute first item",
                    line=first_extends_line_num,
                    col=col,
                    description="HTML comments () are treated as plain text output by Jinja. Outputting text before 'extends' will crash the Python runtime.",
                    original=first_extends_stripped,
                    suggestion="Use Jinja's native comment {# this is a comment #} instead."
                ))
        
        if len(extends_lines) > 1:
            for i in range(1, len(extends_lines)):
                line_num, line, stripped_line = extends_lines[i]
                col = line.find('{% extends') + 1 if '{% extends' in line else 1
                errors.append(SyntaxError(
                    rule="Rule 4: Incorrect extends tag position",
                    line=line_num,
                    col=col,
                    description="Only one extends tag is allowed in a template",
                    original=stripped_line,
                    suggestion="Remove redundant extends tags"
                ))
    return errors


def check_html_comments(template: str) -> List[SyntaxError]:
    """
    Detect dangerous Jinja syntax embedded within HTML comments.
    """
    errors = []
    
    html_comment_pattern = re.compile(r'<!--.*?-->', re.DOTALL)
    
    jinja_pattern = re.compile(r'(\{\{.*?\}\}|\{%.*?%\})', re.DOTALL)
    
    for match in html_comment_pattern.finditer(template):
        content = match.group(0) 
        
        jinja_matches = jinja_pattern.finditer(content)
        
        for j_match in jinja_matches:
            jinja_code = j_match.group(1) 
            
            start_idx = match.start() + j_match.start()
            text_before = template[:start_idx]
            line = text_before.count('\n') + 1
            col = start_idx - text_before.rfind('\n') if '\n' in text_before else start_idx + 1
            
            err = SyntaxError(
                rule="Rule 5: Dangerous Jinja execution inside HTML comment",
                line=line,
                col=col,
                description="Jinja does not recognize HTML comments. The logic inside will still be executed on the server, which may impact performance or cause unexpected crashes.",
                original=jinja_code, 
                suggestion="If you want to disable this Jinja code, wrap it in {# ... #} instead."
            )
            
            try:
                err.severity = "warning"
            except AttributeError:
                pass
                
            errors.append(err)
            
    return errors


def analyze_template(template: str) -> List[SyntaxError]:
    """
    Execute all rule checks.
    """
    syntax_template = mask_raw_blocks(template)
    lines = syntax_template.split('\n')
    errors = []
    
    errors.extend(check_nested_delimiters(syntax_template))
    errors.extend(check_delimiter_mismatch(syntax_template))
    errors.extend(check_tag_logic_pairing(lines))
    errors.extend(check_property_access(lines))
    errors.extend(check_extends_position(lines))
    errors.extend(check_html_comments(syntax_template))
    
    return errors


def _find_closing(text: str, start: int, open_delim: str, close_delim: str) -> int:
    i = start + len(open_delim)
    while i < len(text) - 1:
        if text[i:i+2] == close_delim:
            return i
        i += 1
    return -1


def _get_closing_delimiter(delim_type: str) -> str:
    mapping = {'tag': '%}', 'output': '}}', 'comment': '#}'}
    return mapping.get(delim_type, '?')


def _check_invalid_property_access(content: str, line_num: int, base_col: int) -> List[SyntaxError]:
    errors = []
    already_matched = set()
    
    arrow_pattern = r'([\w\]\)\"\']+)\s*->\s*(\w+)'

    for match in re.finditer(arrow_pattern, content):
        already_matched.add(match.start())
        errors.append(SyntaxError(
            rule="Rule 3: Variable property access syntax error",
            line=line_num,
            col=base_col + match.start(),
            description=f"Used unsupported arrow symbol ->",
            original=match.group(0),
            suggestion=f"Change to: {match.group(1)}.{match.group(2)}"
        ))
    
    for match in re.finditer(r'(\w+)\.\.\s*(\w+)', content):
        already_matched.add(match.start())
        errors.append(SyntaxError(
            rule="Rule 3: Variable property access syntax error",
            line=line_num,
            col=base_col + match.start(),
            description=f"Used redundant dot notation ..",
            original=match.group(0),
            suggestion=f"Change to: {match.group(1)}.{match.group(2)}"
        ))
    
    for match in re.finditer(r'(\w+(?:\.\w+)*)\.\s*$', content):
        if match.start() not in already_matched:
            errors.append(SyntaxError(
                rule="Rule 3: Variable property access syntax error",
                line=line_num,
                col=base_col + match.start(),
                description=f"Property access has trailing dot",
                original=match.group(0),
                suggestion=f"Remove trailing dot: {match.group(1)}"
            ))
    
    for match in re.finditer(r'(\w+)\[(\d+[a-zA-Z_]\w*|\d*[a-zA-Z_][a-zA-Z0-9_]*\d+[a-zA-Z0-9_]*)\]', content):
        errors.append(SyntaxError(
            rule="Rule 3: Variable property access syntax error",
            line=line_num,
            col=base_col + match.start(),
            description=f"Invalid index format [{match.group(2)}]",
            original=match.group(0),
            suggestion=f"Use pure numeric or string index"
        ))
    
    return errors
