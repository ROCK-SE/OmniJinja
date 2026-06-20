import * as vscode from 'vscode';

/**
 * Built-in Filters 
 */
export const BUILTIN_FILTERS: Record<string, any> = {
    "abs": { signature: "abs(x)", description: "Return the absolute value of a number.", caveat: "Only works with numeric types." },
    "first": { signature: "first(seq)", description: "Return the first item of a sequence.", caveat: "Returns undefined for empty sequences." },
    "last": { signature: "last(seq)", description: "Return the last item of a sequence.", caveat: "May be inefficient for large iterators." },
    "min": { signature: "min(value, ...)", description: "Return the smallest item from a sequence.", caveat: "All elements must be comparable." },
    "max": { signature: "max(value, ...)", description: "Return the largest item from a sequence.", caveat: "All elements must be comparable." },
    "length": { signature: "length(obj)", description: "Return the number of items in an object.", caveat: "Returns 0 for objects without a defined length." },
    "default": { signature: "default(value, default_value='', boolean=False)", description: "Return a default value if the original value is undefined.", caveat: "If boolean=True, only False triggers the default." },
    "lower": { signature: "lower(s)", description: "Convert a string to lowercase.", caveat: "Only applicable to strings." },
    "upper": { signature: "upper(s)", description: "Convert a string to uppercase.", caveat: "Only applicable to strings." },
    "sort": { signature: "sort(value, ...)", description: "Sort a sequence.", caveat: "Elements must be comparable." },
    "reverse": { signature: "reverse(value)", description: "Reverse the order of a sequence.", caveat: "Iterators are consumed and converted to lists." },
    "join": { signature: "join(value, d='', attribute=None)", description: "Join items into a string using a delimiter.", caveat: "All items must be string-convertible." },
    "sum": { signature: "sum(iterable, ...)", description: "Sum numeric values in an iterable.", caveat: "All values must be numeric." },
    "list": { signature: "list(value)", description: "Convert a value into a list.", caveat: "Strings are split into characters." },
    "string": { signature: "string(value)", description: "Convert a value to a string.", caveat: "None is converted to an empty string." },
    "int": { signature: "int(value, default=0, base=10)", description: "Convert a value to an integer.", caveat: "Floats are truncated, not rounded." },
    "float": { signature: "float(value, default=0.0)", description: "Convert a value to a float.", caveat: "Invalid values return the default." },
    "escape": { signature: "escape(s)", description: "Escape HTML special characters.", caveat: "Input is first converted to a string." },
    "safe": { signature: "safe(value)", description: "Mark a string as safe HTML.", caveat: "Use only with trusted content to prevent XSS." },
    "replace": { signature: "replace(s, old, new, count=None)", description: "Replace occurrences of a substring.", caveat: "Case-sensitive; regex is not supported." },
    "tojson": { signature: "tojson(value, indent=None)", description: "Serialize an object to a JSON string.", caveat: "Not all Python objects are JSON-serializable." },
    "truncate": { signature: "truncate(s, length=255, ...)", description: "Truncate a string to a given length.", caveat: "HTML tags are not considered." },
    "trim": { signature: "trim(value, chars=None)", description: "Strip leading and trailing characters.", caveat: "Defaults to stripping whitespace." },
    "striptags": { signature: "striptags(value)", description: "Strip SGML/XML tags and normalize whitespace.", caveat: "Returns plain text." },
    "title": { signature: "title(s)", description: "Return a title-cased version of the string.", caveat: "Only applicable to strings." },
    "capitalize": { signature: "capitalize(s)", description: "Capitalize a string.", caveat: "Only applicable to strings." },
    "center": { signature: "center(value, width=80)", description: "Center a value in a field of the given width.", caveat: "Pads with spaces." },
    "indent": { signature: "indent(s, width=4, first=False, blank=False)", description: "Indent lines in a string.", caveat: "Blank and first-line behavior is configurable." },
    "wordcount": { signature: "wordcount(s)", description: "Count words in a string.", caveat: "Uses Jinja's word matching rules." },
    "wordwrap": { signature: "wordwrap(s, width=79, ...)", description: "Wrap text to a given line width.", caveat: "Preserves paragraphs." },
    "unique": { signature: "unique(value, ...)", description: "Return unique items from a sequence.", caveat: "Returns an iterator." },
    "map": { signature: "map(value, attribute)", description: "Apply a filter or extract an attribute.", caveat: "Missing attributes yield undefined." },
    "select": { signature: "select(value, test=None, ...)", description: "Filter a sequence by applying a test.", caveat: "Returns an iterator." },
    "reject": { signature: "reject(value, test=None, ...)", description: "Filter a sequence by rejecting items that pass a test.", caveat: "Returns an iterator." },
    "selectattr": { signature: "selectattr(value, attr, test)", description: "Filter objects by attribute value.", caveat: "Objects without the attribute are skipped." },
    "rejectattr": { signature: "rejectattr(value, attr, test)", description: "Filter objects by rejecting items whose attribute passes a test.", caveat: "Returns an iterator." },
    "attr": { signature: "attr(obj, name)", description: "Get an attribute of an object.", caveat: "Does not fall back to item lookup." },
    "items": { signature: "items(mapping)", description: "Return an iterator over key/value pairs.", caveat: "Returns an empty iterator for undefined values." },
    "dictsort": { signature: "dictsort(value, ...)", description: "Sort a dictionary by key or value.", caveat: "Returns a list of (key, value) tuples." },
    "batch": { signature: "batch(value, linecount, fill_with=None)", description: "Group a sequence into batches.", caveat: "Useful for rows and columns." },
    "slice": { signature: "slice(value, slices, fill_with=None)", description: "Slice an iterator into multiple columns.", caveat: "May add fill values." },
    "groupby": { signature: "groupby(value, attribute, default=None, case_sensitive=False)", description: "Group a sequence by an attribute.", caveat: "Sorts before grouping." },
    "random": { signature: "random(seq)", description: "Return a random item from a sequence.", caveat: "Undefined for empty sequences." },
    "round": { signature: "round(value, precision=0, method='common')", description: "Round a number to a given precision.", caveat: "Returns a float." },
    "filesizeformat": { signature: "filesizeformat(value, binary=False)", description: "Format a number as a human-readable file size.", caveat: "Supports decimal or binary units." },
    "pprint": { signature: "pprint(value)", description: "Pretty-print a variable for debugging.", caveat: "Intended for debugging output." },
    "format": { signature: "format(value, *args, **kwargs)", description: "Apply printf-style string formatting.", caveat: "Prefer the format operator for simple cases." },
    "urlize": { signature: "urlize(value, trim_url_limit=None, nofollow=False, ...)", description: "Convert URLs in plain text into links.", caveat: "Output may be markup." },
    "urlencode": { signature: "urlencode(value)", description: "URL-encode a string or dictionary.", caveat: "Dictionaries become query strings." },
    "xmlattr": { signature: "xmlattr(d, autospace=True)", description: "Create an XML/HTML attribute string from a dictionary.", caveat: "Keys with invalid characters are rejected." },
    "forceescape": { signature: "forceescape(value)", description: "Enforce HTML escaping.", caveat: "Can double-escape existing escaped text." },
    // Aliases
    "d": { signature: "default(...)", description: "Alias for 'default'.", caveat: "Same behavior." },
    "e": { signature: "escape(...)", description: "Alias for 'escape'.", caveat: "Same behavior." },
    "count": { signature: "length(...)", description: "Alias for 'length'.", caveat: "Same behavior." }
};

/**
 * Built-in Tags 
 */
export const BUILTIN_TAGS: Record<string, any> = {
    "for": { 
        syntax: "{% for target in iterable %}...{% endfor %}", 
        description: "Iterate over an iterable and render the block for each item.", 
        caveat: "Loop variables are only available inside the loop body.",
        snippet: "for ${1:item} in ${2:iterable} %}\n\t$0\n{% endfor %}"
    },
    "if": { 
        syntax: "{% if condition %}...{% endif %}", 
        description: "Conditionally render blocks based on the truth value of expressions.", 
        caveat: "Follows Python truthiness rules.",
        snippet: "if ${1:condition} %}\n\t$0\n{% endif %}"
    },
    "set": {
        syntax: "{% set name = value %}",
        description: "Assign a value to a variable within the template.", 
        caveat: "Assignments are scoped to the current context.",
        snippet: "set ${1:name} = ${2:value} %}"
    },
    "block": {
        syntax: "{% block name %}...{% endblock %}",
        description: "Define a named block that can be overridden by child templates.", 
        caveat: "Block names must be unique within a template.",
        snippet: "block ${1:name} %}\n\t$0\n{% endblock %}"
    },
    "extends": {
        syntax: "{% extends template %}",
        description: "Declare template inheritance from a parent template.", 
        caveat: "Must appear before any output.",
        snippet: "extends \"${1:template}\" %}"
    },
    "include": {
        syntax: "{% include template %}",
        description: "Include and render another template within the current one.", 
        caveat: "Included templates share the current context by default.",
        snippet: "include \"${1:template}\" %}"
    },
    "import": {
        syntax: "{% import template as name %}",
        description: "Import macros from another template under a namespace.",
        caveat: "Imported templates do not receive the current context unless requested.",
        snippet: "import \"${1:template}\" as ${2:name} %}"
    },
    "from": {
        syntax: "{% from template import name %}",
        description: "Import selected macros or exported names from another template.",
        caveat: "Use aliases to avoid name collisions.",
        snippet: "from \"${1:template}\" import ${2:name} %}"
    },
    "macro": {
        syntax: "{% macro name(args) %}...{% endmacro %}",
        description: "Define a reusable template function.", 
        caveat: "Variables defined inside a macro are local.",
        snippet: "macro ${1:name}(${2:args}) %}\n\t$0\n{% endmacro %}"
    },
    "call": {
        syntax: "{% call(args) macro_name() %}...{% endcall %}",
        description: "Invoke a macro and pass a block of content to it.", 
        caveat: "The macro must explicitly call caller() to render the block.",
        snippet: "call(${1:args}) ${2:macro}() %}\n\t$0\n{% endcall %}"
    },
    "filter": {
        syntax: "{% filter name %}...{% endfilter %}",
        description: "Apply a filter to the entire contents of a block.", 
        caveat: "All content inside the block is filtered.",
        snippet: "filter ${1:filter_name} %}\n\t$0\n{% endfilter %}"
    },
    "with": {
        syntax: "{% with name = value %}...{% endwith %}",
        description: "Create a new inner scope with temporary variables.", 
        caveat: "Variables inside the block do not exist outside it.",
        snippet: "with ${1:name} = ${2:value} %}\n\t$0\n{% endwith %}"
    },
    "raw": {
        syntax: "{% raw %}...{% endraw %}",
        description: "Render content verbatim without processing Jinja syntax.", 
        caveat: "Jinja syntax inside raw blocks is ignored entirely.",
        snippet: "raw %}\n\t$0\n{% endraw %}"
    },
    "autoescape": {
        syntax: "{% autoescape true|false %}...{% endautoescape %}",
        description: "Enable or disable autoescaping for a block.",
        caveat: "Use cautiously when rendering HTML.",
        snippet: "autoescape ${1:true} %}\n\t$0\n{% endautoescape %}"
    },
    "elif": {
        syntax: "{% elif condition %}",
        description: "Add another conditional branch inside an if block.",
        caveat: "Only valid inside an if block.",
        snippet: "elif ${1:condition} %}"
    },
    "else": {
        syntax: "{% else %}",
        description: "Add a fallback branch inside if or for blocks.",
        caveat: "Only valid inside supported block tags.",
        snippet: "else %}"
    },
    "endif": { syntax: "{% endif %}", description: "Close an if block.", caveat: "Must match an open if block.", snippet: "endif %}" },
    "endfor": { syntax: "{% endfor %}", description: "Close a for block.", caveat: "Must match an open for block.", snippet: "endfor %}" },
    "endblock": { syntax: "{% endblock %}", description: "Close a block tag.", caveat: "Must match an open block tag.", snippet: "endblock %}" },
    "endmacro": { syntax: "{% endmacro %}", description: "Close a macro block.", caveat: "Must match an open macro tag.", snippet: "endmacro %}" },
    "endcall": { syntax: "{% endcall %}", description: "Close a call block.", caveat: "Must match an open call tag.", snippet: "endcall %}" },
    "endfilter": { syntax: "{% endfilter %}", description: "Close a filter block.", caveat: "Must match an open filter tag.", snippet: "endfilter %}" },
    "endwith": { syntax: "{% endwith %}", description: "Close a with block.", caveat: "Must match an open with tag.", snippet: "endwith %}" },
    "endraw": { syntax: "{% endraw %}", description: "Close a raw block.", caveat: "Must match an open raw tag.", snippet: "endraw %}" },
    "endautoescape": {
        syntax: "{% endautoescape %}",
        description: "Close an autoescape block.",
        caveat: "Must match an open autoescape tag.",
        snippet: "endautoescape %}"
    }
};

/**
 * Built-in Tests (Used with 'is' keyword)
 */
export const BUILTIN_TESTS: Record<string, any> = {
    "defined": { signature: "is defined", description: "Return true if the variable is defined." },
    "undefined": { signature: "is undefined", description: "Return true if the variable is undefined." },
    "none": { signature: "is none", description: "Return true if the variable is none." },
    "boolean": { signature: "is boolean", description: "Return true if the object is a boolean." },
    "true": { signature: "is true", description: "Return true if the object is true." },
    "false": { signature: "is false", description: "Return true if the object is false." },
    "string": { signature: "is string", description: "Return true if the variable is a string." },
    "number": { signature: "is number", description: "Return true if the variable is a number." },
    "integer": { signature: "is integer", description: "Return true if the object is an integer." },
    "float": { signature: "is float", description: "Return true if the object is a float." },
    "iterable": { signature: "is iterable", description: "Return true if the object is iterable." },
    "sequence": { signature: "is sequence", description: "Return true if the object is a sequence." },
    "mapping": { signature: "is mapping", description: "Return true if the object is a mapping." },
    "callable": { signature: "is callable", description: "Return true if the object can be called." },
    "sameas": { signature: "is sameas(value)", description: "Return true if two objects are the same object." },
    "escaped": { signature: "is escaped", description: "Return true if the value is already escaped." },
    "lower": { signature: "is lower", description: "Return true if the value is lowercase." },
    "upper": { signature: "is upper", description: "Return true if the value is uppercase." },
    "divisibleby": { signature: "is divisibleby(num)", description: "Return true if the value is divisible by a number." },
    "even": { signature: "is even", description: "Return true if the variable is even." },
    "odd": { signature: "is odd", description: "Return true if the variable is odd." },
    "eq": { signature: "is eq(value)", description: "Alias for equal comparison." },
    "equalto": { signature: "is equalto(value)", description: "Alias for equal comparison." },
    "ne": { signature: "is ne(value)", description: "Alias for not-equal comparison." },
    "lt": { signature: "is lt(value)", description: "Alias for less-than comparison." },
    "lessthan": { signature: "is lessthan(value)", description: "Alias for less-than comparison." },
    "le": { signature: "is le(value)", description: "Alias for less-than-or-equal comparison." },
    "gt": { signature: "is gt(value)", description: "Alias for greater-than comparison." },
    "greaterthan": { signature: "is greaterthan(value)", description: "Alias for greater-than comparison." },
    "ge": { signature: "is ge(value)", description: "Alias for greater-than-or-equal comparison." },
    "==": { signature: "is ==(value)", description: "Alias for equal comparison." },
    "!=": { signature: "is !=(value)", description: "Alias for not-equal comparison." },
    "<": { signature: "is <(value)", description: "Alias for less-than comparison." },
    "<=": { signature: "is <=(value)", description: "Alias for less-than-or-equal comparison." },
    ">": { signature: "is >(value)", description: "Alias for greater-than comparison." },
    ">=": { signature: "is >=(value)", description: "Alias for greater-than-or-equal comparison." },
    "in": { signature: "is in(seq)", description: "Return true if the value is contained in a sequence." },
    "filter": { signature: "is filter", description: "Return true if a filter exists by name." },
    "test": { signature: "is test", description: "Return true if a test exists by name." }
};

/**
 * Built-in Type Methods
 * Provides method completions for common Python types (dict, list, str)
 * that are passed as context variables into Jinja2 templates.
 * Each method includes signature, args for snippet generation, and docstring for hover info.
 */
export const BUILTIN_TYPE_METHODS: Record<string, Record<string, any>> = {
    "Dictionary": {
        "items": {
            __type__: "Function",
            signature: "items()",
            docstring: "Return an iterator over the dictionary's (key, value) pairs.",
            args: []
        },
        "keys": {
            __type__: "Function",
            signature: "keys()",
            docstring: "Return an iterator over the dictionary's keys.",
            args: []
        },
        "values": {
            __type__: "Function",
            signature: "values()",
            docstring: "Return an iterator over the dictionary's values.",
            args: []
        },
        "get": {
            __type__: "Function",
            signature: "get(key, default=None)",
            docstring: "Return the value for key if key is in the dictionary, else default.",
            args: ["key", "default"]
        },
        "update": {
            __type__: "Function",
            signature: "update(other)",
            docstring: "Update the dictionary with the key/value pairs from other.",
            args: ["other"]
        },
        "pop": {
            __type__: "Function",
            signature: "pop(key, default=None)",
            docstring: "Remove and return the value for key if key is in the dictionary, else default.",
            args: ["key", "default"]
        }
    },
    "List": {
        "append": {
            __type__: "Function",
            signature: "append(item)",
            docstring: "Add an item to the end of the list.",
            args: ["item"]
        },
        "pop": {
            __type__: "Function",
            signature: "pop(index=-1)",
            docstring: "Remove and return the item at the given index.",
            args: ["index"]
        },
        "index": {
            __type__: "Function",
            signature: "index(value, start=0, stop=None)",
            docstring: "Return the first index of value in the list.",
            args: ["value", "start", "stop"]
        },
        "count": {
            __type__: "Function",
            signature: "count(value)",
            docstring: "Return the number of occurrences of value in the list.",
            args: ["value"]
        },
        "sort": {
            __type__: "Function",
            signature: "sort(key=None, reverse=False)",
            docstring: "Sort the list in place.",
            args: ["key", "reverse"]
        },
        "reverse": {
            __type__: "Function",
            signature: "reverse()",
            docstring: "Reverse the list in place.",
            args: []
        },
        "extend": {
            __type__: "Function",
            signature: "extend(iterable)",
            docstring: "Extend the list by appending elements from the iterable.",
            args: ["iterable"]
        }
    },
    "String": {
        "upper": {
            __type__: "Function",
            signature: "upper()",
            docstring: "Return a copy of the string converted to uppercase.",
            args: []
        },
        "lower": {
            __type__: "Function",
            signature: "lower()",
            docstring: "Return a copy of the string converted to lowercase.",
            args: []
        },
        "capitalize": {
            __type__: "Function",
            signature: "capitalize()",
            docstring: "Return a copy of the string with its first character capitalized.",
            args: []
        },
        "title": {
            __type__: "Function",
            signature: "title()",
            docstring: "Return a titlecased version of the string.",
            args: []
        },
        "strip": {
            __type__: "Function",
            signature: "strip(chars=None)",
            docstring: "Return a copy of the string with leading and trailing whitespace removed.",
            args: ["chars"]
        },
        "split": {
            __type__: "Function",
            signature: "split(sep=None, maxsplit=-1)",
            docstring: "Return a list of the words in the string using sep as the delimiter.",
            args: ["sep", "maxsplit"]
        },
        "join": {
            __type__: "Function",
            signature: "join(iterable)",
            docstring: "Concatenate any number of strings using this string as separator.",
            args: ["iterable"]
        },
        "replace": {
            __type__: "Function",
            signature: "replace(old, new, count=-1)",
            docstring: "Return a copy with all occurrences of substring old replaced by new.",
            args: ["old", "new", "count"]
        },
        "startswith": {
            __type__: "Function",
            signature: "startswith(prefix, start=0, end=None)",
            docstring: "Return True if the string starts with the specified prefix.",
            args: ["prefix", "start", "end"]
        },
        "endswith": {
            __type__: "Function",
            signature: "endswith(suffix, start=0, end=None)",
            docstring: "Return True if the string ends with the specified suffix.",
            args: ["suffix", "start", "end"]
        },
        "find": {
            __type__: "Function",
            signature: "find(sub, start=0, end=None)",
            docstring: "Return the lowest index where substring sub is found.",
            args: ["sub", "start", "end"]
        },
        "format": {
            __type__: "Function",
            signature: "format(*args, **kwargs)",
            docstring: "Perform string formatting.",
            args: ["...args"]
        }
    }
};

/**
 * Built-in Globals
 */
export const BUILTIN_GLOBALS: Record<string, any> = {
    "range": { signature: "range([start], stop, [step])", description: "Return a list containing an arithmetic progression of integers.", snippet: "range(${1:stop})" },
    "dict": { signature: "dict(...)", description: "Create a dictionary object.", snippet: "dict()" },
    "cycler": { signature: "cycler(...items)", description: "Cycle through values across repeated template calls.", snippet: "cycler(${1:items})" },
    "joiner": { signature: "joiner(separator=', ')", description: "Return a helper that emits a separator after its first call.", snippet: "joiner()" },
    "namespace": { signature: "namespace(...)", description: "Create a mutable namespace object for template state.", snippet: "namespace()" },
    "lipsum": { signature: "lipsum(...)", description: "Generate placeholder lorem ipsum text.", snippet: "lipsum()" },
    "url_for": { signature: "url_for(endpoint, **values)", description: "Flask helper that builds a URL for an endpoint.", snippet: "url_for('${1:endpoint}')" },
    "get_flashed_messages": { signature: "get_flashed_messages(...)", description: "Flask helper that returns flashed messages.", snippet: "get_flashed_messages()" },
    "config": { signature: "config", description: "Flask application configuration exposed to templates." },
    "request": { signature: "request", description: "The current Flask request object exposed to templates." },
    "session": { signature: "session", description: "The current Flask session object exposed to templates." },
    "g": { signature: "g", description: "Flask's request-local global namespace exposed to templates." },
    "true": { signature: "true", description: "Boolean true constant." },
    "false": { signature: "false", description: "Boolean false constant." },
    "none": { signature: "none", description: "Null/none constant." },
    "super": { signature: "super()", description: "Render the contents of the parent block.", snippet: "super()" }
};
