# OmniJinja
**An Omni VSCode Extension for the Jinja Template Engine.**

OmniJinja goes far beyond standard syntax highlighting. It acts as an intelligent bridge between your Python backend (like Flask) and your frontend Jinja2/HTML templates. Powered by a background analysis engine, it deeply understands your custom context variables, filters, macros, and data flow etc.

---

## Key Features

### Cross-File Data Flow Validation
OmniJinja analyzes the "Supply" from your Python files and the "Demand" from your templates. It provides real-time diagnostics (squiggly lines) in both your Python and HTML files if:
* You forget to pass a required variable in `render_template`.
* You iterate over a variable in Jinja that isn't actually an Iterable in Python.
* You attempt to call a variable as a function when it isn't callable.

### Automated Quick Fixes & Silent Ignores
* **Auto-Fix**: Detects structural Jinja syntax errors and provides a one-click Quick Fix to repair the template code automatically.
* **Silent Ignore**: Annoyed by a specific warning? Use the Quick Fix menu to "Ignore this warning (Locally)". The warning will vanish instantly.

### Intelligent Auto-Completion
Context-aware IntelliSense that activates when you type `{{`, `{%`, `|`, or `.`:
* **Context Variables**: Auto-completes properties of objects passed directly from your Python backend.
* **Built-ins & Custom Filters**: Full support for Jinja built-in tags, filters, tests, and globals. It even auto-completes **custom filters** defined in your Python source code!
* **Template Paths**: Auto-completes file paths when using `{% extends ... %}` or `{% include ... %}`.

### Rich Hover Docs & Signature Help
* **Hover**: Hover over any Jinja variable, custom filter, or built-in tag to see its Python type, signature, and Markdown-formatted docstring.
* **Signature Help**: When calling a macro or custom filter (e.g., `{{ user.get_avatar(|) }}`), OmniJinja displays real-time parameter hints just like a standard programming language.

### Go-To Definition
Navigate massive codebases with ease. **Ctrl+Click** (or **Cmd+Click**) on a context variable or custom filter in your Jinja template to instantly jump to its exact definition line in your Python source code.

---

## Requirements

OmniJinja runs a lightweight Python analysis engine in the background. To use this extension, you must meet the following requirement:

**Python Environment**: Python must be installed on your system. The extension will automatically attempt to use `python3` or `python` from your system's PATH.

---

## Usage

OmniJinja activates automatically when you open any of the following file types:
* `.py`
* `.html`
* `.jinja`, `.jinja2`, `.j2`

Simply open a workspace containing your Python backend and template files. OmniJinja will briefly scan your files in the background to build its intelligent context registry. 

Start typing `{{` or `{%` in your templates, or hover over a variable, to see the magic happen!

---

## Known Issues

* **Silent Ignore Persistence**: Currently, diagnostics ignored via the "Ignore Locally" quick-fix are stored in memory and will reappear if you restart the VS Code window.
* **Initial Scan Delay**: For extremely large projects with hundreds of complex Python files, the initial workspace scan upon activation might take a few seconds.

---

**Enjoy building with Jinja!** ```