# models.py
from dataclasses import dataclass
from enum import Enum


@dataclass
class SyntaxError:
    """
    Syntax error information (shared data structure).
    
    This dataclass stores detailed information about a detected syntax error
    in the template, including its location, description, and suggested fix.
    
    Attributes:
        rule: The rule number and name that was violated
        line: Line number where the error occurs
        col: Column number where the error starts
        description: Detailed description of the error
        original: The original erroneous text
        suggestion: Suggested fix for the error
    """
    rule: str
    line: int
    col: int
    description: str
    original: str
    suggestion: str


class State(Enum):
    """
    Parser state enumeration (used by detection module).
    
    This enum tracks the current parsing context when scanning through
    a template to determine what type of delimiter block we're inside.
    
    Values:
        NORMAL: In normal text outside any template delimiters
        IN_TAG: Inside a {% %} tag block
        IN_OUTPUT: Inside a {{ }} output block
        IN_COMMENT: Inside a {# #} comment block
    """
    NORMAL = "normal"           # Normal text
    IN_TAG = "in_tag"          # Inside {% %}
    IN_OUTPUT = "in_output"    # Inside {{ }}
    IN_COMMENT = "in_comment"  # Inside {# #}
