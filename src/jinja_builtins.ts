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
    "unique": { signature: "unique(value, ...)", description: "Return unique items from a sequence.", caveat: "Returns an iterator." },
    "map": { signature: "map(value, attribute)", description: "Apply a filter or extract an attribute.", caveat: "Missing attributes yield undefined." },
    "selectattr": { signature: "selectattr(value, attr, test)", description: "Filter objects by attribute value.", caveat: "Objects without the attribute are skipped." },
    "dictsort": { signature: "dictsort(value, ...)", description: "Sort a dictionary by key or value.", caveat: "Returns a list of (key, value) tuples." },
    "urlencode": { signature: "urlencode(value)", description: "URL-encode a string or dictionary.", caveat: "Dictionaries become query strings." },
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
    }
};

/**
 * Built-in Tests (Used with 'is' keyword)
 */
export const BUILTIN_TESTS: Record<string, any> = {
    "defined": { signature: "is defined", description: "Return true if the variable is defined." },
    "undefined": { signature: "is undefined", description: "Return true if the variable is undefined." },
    "none": { signature: "is none", description: "Return true if the variable is none." },
    "string": { signature: "is string", description: "Return true if the variable is a string." },
    "number": { signature: "is number", description: "Return true if the variable is a number." },
    "iterable": { signature: "is iterable", description: "Return true if the object is iterable." },
    "even": { signature: "is even", description: "Return true if the variable is even." },
    "odd": { signature: "is odd", description: "Return true if the variable is odd." }
};

/**
 * Built-in Globals
 */
export const BUILTIN_GLOBALS: Record<string, any> = {
    "range": { signature: "range([start], stop, [step])", description: "Return a list containing an arithmetic progression of integers.", snippet: "range(${1:stop})" },
    "loop": { signature: "loop", description: "The loop object available inside for-loops, containing index, length, etc." },
    "super": { signature: "super()", description: "Render the contents of the parent block.", snippet: "super()" }
};