import tkinter as tk  # GUI toolkit for creating the user interface
import builtins  # Provides access to Python's built-in functions, exceptions, and attributes
import importlib  # Allows dynamic importing of modules, useful for inspecting installed packages
import subprocess  # Enables running external commands, like 'pip freeze'
import inspect  # Provides tools for examining live objects, like getting function signatures and docstrings
import requests  # Used for making HTTP requests, specifically to fetch data from PyPI
import json  # For encoding and decoding JSON data, used for caching
import os  # Provides functions for interacting with the operating system, like file paths and directories
import sys  # Provides access to system-specific parameters and functions, like sys.path
import site  # Provides access to site-specific configuration, like site-packages directories
import time  # For time-related functions, used in cache expiry calculations
from tkinter import font, scrolledtext, messagebox, Menu  # Specific Tkinter widgets and modules
import re  # Regular expression operations, used for parsing docstrings and highlighting
import webbrowser  # Allows opening web browsers, used for PyPI links

# --- Global Configuration and Directories ---
# Define directory paths for caching and user notes.
# os.path.expanduser("~") gets the user's home directory, ensuring cross-platform compatibility.
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".pyref_cache")
NOTES_DIR = os.path.join(os.path.expanduser("~"), ".pyref_notes")

# Define specific file paths within the cache directory for different data types.
STANDARD_CACHE_FILE = os.path.join(CACHE_DIR, "standard_commands.json")
INSTALLED_CACHE_FILE = os.path.join(CACHE_DIR, "installed_modules.json")
PYPI_INDEX_CACHE_FILE = os.path.join(CACHE_DIR, "pypi_index.json")
PYPI_DETAIL_CACHE_DIR = os.path.join(CACHE_DIR, "pypi_details")

# --- Cache Expiry Settings ---
# Define how long different types of cached data remain valid (in seconds).
# This prevents displaying stale information and ensures periodic updates.
CACHE_EXPIRY_SECONDS = {
    "standard": 3600 * 24 * 30,  # Standard commands cache (30 days) - rarely changes
    "installed": 3600 * 24 * 7,   # Installed modules cache (7 days) - updates when pip changes
    "pypi_index": 3600 * 24,      # PyPI index cache (1 day) - frequently updated
    "pypi_detail": 3600 * 24 * 7  # Individual PyPI package details (7 days)
}

# --- Cache Management Functions ---

def ensure_cache_dir():
    """Ensures that the necessary cache and notes directories exist.
    
    If they don't exist, they are created. This prevents FileNotFoundError.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)  # Creates the main cache directory if it doesn't exist
    os.makedirs(NOTES_DIR, exist_ok=True)  # Creates the notes directory if it doesn't exist
    os.makedirs(PYPI_DETAIL_CACHE_DIR, exist_ok=True) # Creates the specific directory for PyPI package details

def load_cache(cache_file: str, cache_type: str):
    """Loads data from a specified cache file if it's not expired.

    Args:
        cache_file (str): The full path to the cache file.
        cache_type (str): The type of cache (e.g., "standard", "installed")
                          to determine its expiry time from CACHE_EXPIRY_SECONDS.

    Returns:
        dict or list or None: The loaded data if valid and not expired, otherwise None.
    """
    ensure_cache_dir()  # Make sure directories are ready before trying to load/save
    if os.path.exists(cache_file):
        file_mod_time = os.path.getmtime(cache_file)  # Get the last modification time of the cache file
        # Check if the cache file is still valid (not expired)
        if (time.time() - file_mod_time) < CACHE_EXPIRY_SECONDS.get(cache_type, 0):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)  # Load and return the JSON data
            except json.JSONDecodeError:
                # Handle corrupted JSON files
                print(f"Error decoding JSON from {cache_file}. Cache will be refreshed.")
                os.remove(cache_file)  # Delete the corrupted cache to force a refresh
                return None
            except Exception as e:
                # Catch any other unexpected errors during file loading
                print(f"Unexpected error loading cache from {cache_file}: {e}")
                return None
    return None  # Return None if cache file doesn't exist or is expired

def save_cache(data, cache_file: str):
    """Saves data to a specified cache file in JSON format.

    Args:
        data: The data (e.g., list, dictionary) to be saved.
        cache_file (str): The full path to the cache file.
    """
    ensure_cache_dir()  # Ensure directories exist before saving
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)  # Save data as pretty-printed JSON
    except IOError as e:
        # Handle potential errors during file writing
        print(f"Error saving cache to {cache_file}: {e}")

# --- PyRef GUI Class ---
class PythonHelperGUI:
    """The main application class for PyRef, handling the GUI and logic."""

    def __init__(self, master: tk.Tk):
        """Initializes the PyRef GUI application.

        Args:
            master (tk.Tk): The root Tkinter window.
        """
        self.master = master  # Store the root Tkinter window
        master.title("PyRef")  # Set the window title
        master.geometry("1000x700")  # Set the initial window size

        self._setup_sys_path()  # Configure system path for module imports

        # --- Curated Syntax Overrides for C-implemented Built-ins ---
        # This dictionary provides explicit syntax, parameters, and simple examples for
        # built-in functions that `inspect.signature()` cannot properly introspect
        # (e.g., because they are implemented in C). This ensures clear documentation
        # for these common functions.
        self._builtin_syntax_override = {
            "abs": {
                "syntax": "abs(number)",
                "parameters": [
                    {"name": "number", "description": "A numeric value (integer, float, or complex)."}
                ],
                "example": "x = abs(-7.25)\nprint(x)  # Output: 7.25"
            },
            "aiter": {
                "syntax": "aiter(async_iterable)",
                "parameters": [
                    {"name": "async_iterable", "description": "An asynchronous iterable object."}
                ],
                "example": "async def my_async_gen():\n    yield 1\n    yield 2\n\nasync def main():\n    it = aiter(my_async_gen())\n    print(await anext(it)) # Output: 1\n\nimport asyncio\nasyncio.run(main())"
            },
            "all": {
                "syntax": "all(iterable)",
                "parameters": [
                    {"name": "iterable", "description": "An iterable (e.g., list, tuple, string) containing items to check."}
                ],
                "example": "all([True, True, False])  # Output: False\nall([1, 2, 3])      # Output: True (all are truthy)"
            },
            "anext": {
                "syntax": "anext(async_iterator[, default])",
                "parameters": [
                    {"name": "async_iterator", "description": "An asynchronous iterator object."},
                    {"name": "default", "description": "Optional. The value to return if the iterator is exhausted."}
                ],
                "example": "async def my_async_gen():\n    yield 1\n    yield 2\n\nasync def main():\n    it = aiter(my_async_gen())\n    print(await anext(it))  # Output: 1\n    print(await anext(it))  # Output: 2\n    print(await anext(it, 'End')) # Output: End\n\nimport asyncio\nasyncio.run(main())"
            },
            "any": {
                "syntax": "any(iterable)",
                "parameters": [
                    {"name": "iterable", "description": "An iterable containing items to check."}
                ],
                "example": "any([False, False, True]) # Output: True\nany([])             # Output: False"
            },
            "ascii": {
                "syntax": "ascii(object)",
                "parameters": [
                    {"name": "object", "description": "An object to represent as an ASCII string."}
                ],
                "example": "ascii('€')  # Output: '\\u20ac'\nascii('hello') # Output: 'hello'"
            },
            "bin": {
                "syntax": "bin(number)",
                "parameters": [
                    {"name": "number", "description": "An integer."}
                ],
                "example": "bin(10)  # Output: '0b1010'"
            },
            "bool": {
                "syntax": "bool([x])",
                "parameters": [
                    {"name": "x", "description": "An optional value to convert to boolean. If omitted, returns False."}
                ],
                "example": "bool(0)     # Output: False\nbool('hello') # Output: True"
            },
            "breakpoint": {
                "syntax": "breakpoint(*args, **kwargs)",
                "parameters": [
                    {"name": "*args, **kwargs", "description": "Arguments passed to the debugger callable."}
                ],
                "example": "def my_func():\n    a = 10\n    breakpoint() # Execution will pause here\n    b = 20\n    print(a + b)\n\n# To use:\n# Run your script, when it hits breakpoint(), you'll enter the debugger (e.g., pdb).\n# Type 'c' to continue execution."
            },
            "bytes": {
                "syntax": "bytes([source[, encoding[, errors]]])",
                "parameters": [
                    {"name": "source", "description": "Optional. An int, iterable of ints, str, or buffer object."}
                ],
                "example": "bytes(5)          # Output: b'\\x00\\x00\\x00\\x00\\x00'\nb = 'hello'.encode('utf-8')\nprint(b)          # Output: b'hello'"
            },
            "bytearray": {
                "syntax": "bytearray([source[, encoding[, errors]]])",
                "parameters": [
                    {"name": "source", "description": "Optional. An int, iterable of ints, str, or buffer object."}
                ],
                "example": "arr = bytearray(b'hello')\narr[0] = ord('J')\nprint(arr) # Output: bytearray(b'Jello')"
            },
            "callable": {
                "syntax": "callable(object)",
                "parameters": [
                    {"name": "object", "description": "The object to check."}
                ],
                "example": "def func(): pass\nprint(callable(func))   # Output: True\nprint(callable(10))     # Output: False"
            },
            "chr": {
                "syntax": "chr(i)",
                "parameters": [
                    {"name": "i", "description": "An integer representing a Unicode code point."}
                ],
                "example": "chr(97)  # Output: 'a'"
            },
            "compile": {
                "syntax": "compile(source, filename, mode, flags=0, dont_inherit=False, optimize=-1)",
                "parameters": [
                    {"name": "source", "description": "The source code as a string, bytes, or AST object."},
                    {"name": "filename", "description": "The filename (used for error messages)."},
                    {"name": "mode", "description": "Specifies the kind of code: 'eval', 'exec', or 'single'."}
                ],
                "example": "code_obj = compile('a = 10\\nprint(a)', '<string>', 'exec')\nexec(code_obj) # Output: 10"
            },
            "copyright": {
                "syntax": "copyright",
                "parameters": [],
                "example": "print(copyright) # Displays Python's copyright notice"
            },
            "credits": {
                "syntax": "credits",
                "parameters": [],
                "example": "print(credits) # Displays Python's credits"
            },
            "dict": {
                "syntax": "dict(**kwargs) or dict(mapping, **kwargs) or dict(iterable, **kwargs)",
                "parameters": [
                    {"name": "kwargs", "description": "Keyword arguments where keys are strings and values are dictionary values."},
                    {"name": "mapping", "description": "A dictionary or other mapping object."},
                    {"name": "iterable", "description": "An iterable of key-value pairs (e.g., a list of tuples)."}
                ],
                "example": "d1 = dict(a=1, b=2)  # Output: {'a': 1, 'b': 2}\nd2 = dict([('c', 3), ('d', 4)]) # Output: {'c': 3, 'd': 4}"
            },
            "dir": {
                "syntax": "dir([object])",
                "parameters": [
                    {"name": "object", "description": "Optional. An object. If omitted, returns names in the current scope."}
                ],
                "example": "dir()          # List names in current scope\ndir([])        # List methods of a list"
            },
            "divmod": {
                "syntax": "divmod(a, b)",
                "parameters": [
                    {"name": "a", "description": "Dividend."},
                    {"name": "b", "description": "Divisor."}
                ],
                "example": "divmod(7, 3)  # Output: (2, 1) (quotient, remainder)"
            },
            "enumerate": {
                "syntax": "enumerate(iterable, start=0)",
                "parameters": [
                    {"name": "iterable", "description": "A sequence, an iterator, or some other object that supports iteration."},
                    {"name": "start", "description": "Optional. The index value for the first item (default is 0)."}
                ],
                "example": "for i, item in enumerate(['a', 'b', 'c']):\n    print(f'{i}: {item}')\n# Output:\n# 0: a\n# 1: b\n# 2: c"
            },
            "eval": {
                "syntax": "eval(expression[, globals[, locals]])",
                "parameters": [
                    {"name": "expression", "description": "A string containing a Python expression."},
                    {"name": "globals", "description": "Optional. A dictionary of global names."},
                    {"name": "locals", "description": "Optional. A dictionary of local names."}
                ],
                "example": "x = 10\nprint(eval('x + 5'))  # Output: 15\nprint(eval('sum([1, 2, 3])')) # Output: 6"
            },
            "exec": {
                "syntax": "exec(object[, globals[, locals]])",
                "parameters": [
                    {"name": "object", "description": "A string containing Python statements, or a code object."},
                    {"name": "globals", "description": "Optional. A dictionary of global names."},
                    {"name": "locals", "description": "Optional. A dictionary of local names."}
                ],
                "example": "code = 'for i in range(3): print(i)'\nexec(code)\n# Output:\n# 0\n# 1\n# 2"
            },
            "exit": {
                "syntax": "exit([code=None])",
                "parameters": [
                    {"name": "code", "description": "Optional. An exit status code (default None)."}
                ],
                "example": "import sys\n# exit()\n# exit('Exiting program')\n# Note: Calling exit() directly in some environments (like IDLE) might just raise SystemExit"
            },
            "filter": {
                "syntax": "filter(function, iterable)",
                "parameters": [
                    {"name": "function", "description": "A function to test if an element of an iterable passes a condition."},
                    {"name": "iterable", "description": "An iterable that is to be filtered."}
                ],
                "example": "numbers = [1, 2, 3, 4, 5]\neven_numbers = list(filter(lambda x: x % 2 == 0, numbers))\nprint(even_numbers) # Output: [2, 4]"
            },
            "float": {
                "syntax": "float([x])",
                "parameters": [
                    {"name": "x", "description": "Optional. A number or string representing a number."}
                ],
                "example": "float('3.14') # Output: 3.14\nfloat(5)      # Output: 5.0"
            },
            "format": {
                "syntax": "format(value[, format_spec])",
                "parameters": [
                    {"name": "value", "description": "The value to be formatted."},
                    {"name": "format_spec", "description": "Optional. A format specifier string (e.g., '.2f', '>10s')."}
                ],
                "example": "format(3.14159, '.2f') # Output: '3.14'\nformat(123, '0>5')    # Output: '00123'"
            },
            "frozenset": {
                "syntax": "frozenset([iterable])",
                "parameters": [
                    {"name": "iterable", "description": "Optional. An iterable from which to initialize the frozenset."}
                ],
                "example": "fs = frozenset([1, 2, 3])\nprint(fs) # Output: frozenset({1, 2, 3})"
            },
            "getattr": {
                "syntax": "getattr(object, name[, default])",
                "parameters": [
                    {"name": "object", "description": "The object to get the attribute from."},
                    {"name": "name", "description": "A string representing the attribute's name."},
                    {"name": "default", "description": "Optional. The value to return if the named attribute does not exist."}
                ],
                "example": "class MyClass:\n    value = 10\nobj = MyClass()\nprint(getattr(obj, 'value'))   # Output: 10\nprint(getattr(obj, 'other', 'default')) # Output: default"
            },
            "globals": {
                "syntax": "globals()",
                "parameters": [],
                "example": "print(globals()) # Returns a dictionary of the current global symbol table"
            },
            "hasattr": {
                "syntax": "hasattr(object, name)",
                "parameters": [
                    {"name": "object", "description": "The object to check."},
                    {"name": "name", "description": "A string representing the attribute's name."}
                ],
                "example": "class MyClass:\n    value = 10\nobj = MyClass()\nprint(hasattr(obj, 'value'))  # Output: True\nprint(hasattr(obj, 'other'))  # Output: False"
            },
            "hash": {
                "syntax": "hash(object)",
                "parameters": [
                    {"name": "object", "description": "The object to hash."}
                ],
                "example": "hash('hello') # Returns an integer hash value"
            },
            "help": {
                "syntax": "help([object])",
                "parameters": [
                    {"name": "object", "description": "Optional. The object for which to display help."}
                ],
                "example": "help(list)   # Displays help for the list type\nhelp('modules') # Lists all available modules"
            },
            "hex": {
                "syntax": "hex(number)",
                "parameters": [
                    {"name": "number", "description": "An integer."}
                ],
                "example": "hex(255)  # Output: '0xff'"
            },
            "id": {
                "syntax": "id(object)",
                "parameters": [
                    {"name": "object", "description": "Any object."}
                ],
                "example": "x = 10\nid(x)  # Returns the identity of x (an integer)"
            },
            "input": {
                "syntax": "input([prompt])",
                "parameters": [
                    {"name": "prompt", "description": "Optional. A string that is printed to the console before reading input."}
                ],
                "example": "name = input('Enter your name: ')\nprint(f'Hello, {name}')"
            },
            "int": {
                "syntax": "int([x=0]) or int(x, base=10)",
                "parameters": [
                    {"name": "x", "description": "Optional. A number or string to convert to an integer."},
                    {"name": "base", "description": "Optional. The base of the number if `x` is a string (default 10)."}
                ],
                "example": "int(3.14)   # Output: 3\nint('FF', 16) # Output: 255"
            },
            "isinstance": {
                "syntax": "isinstance(object, classinfo)",
                "parameters": [
                    {"name": "object", "description": "The object to check."},
                    {"name": "classinfo", "description": "A class, type, or tuple of classes and types."}
                ],
                "example": "isinstance(10, int)        # Output: True\nisinstance('hello', (str, list)) # Output: True"
            },
            "issubclass": {
                "syntax": "issubclass(class, classinfo)",
                "parameters": [
                    {"name": "class", "description": "The class to check."},
                    {"name": "classinfo", "description": "A class, type, or tuple of classes and types."}
                ],
                "example": "class A: pass\nclass B(A): pass\nissubclass(B, A) # Output: True"
            },
            "iter": {
                "syntax": "iter(object[, sentinel])",
                "parameters": [
                    {"name": "object", "description": "An object that supports iteration (e.g., list, tuple) or a callable."},
                    {"name": "sentinel", "description": "Optional. If provided, `object` must be a callable; iteration stops when `object()` returns `sentinel`."}
                ],
                "example": "my_list = [1, 2, 3]\nmy_iter = iter(my_list)\nprint(next(my_iter)) # Output: 1"
            },
            "len": {
                "syntax": "len(s)",
                "parameters": [
                    {"name": "s", "description": "An object that has a length (e.g., sequence, collection, string)."}
                ],
                "example": "len('hello')  # Output: 5\nlen([1, 2, 3]) # Output: 3"
            },
            "license": {
                "syntax": "license",
                "parameters": [],
                "example": "print(license) # Displays Python's license information"
            },
            "list": {
                "syntax": "list([iterable])",
                "parameters": [
                    {"name": "iterable", "description": "Optional. An iterable from which to create the list."}
                ],
                "example": "my_list = list('abc')\nprint(my_list) # Output: ['a', 'b', 'c']"
            },
            "locals": {
                "syntax": "locals()",
                "parameters": [],
                "example": "def my_func():\n    x = 10\n    y = 20\n    print(locals()) # Returns a dictionary of the current local symbol table\nmy_func()"
            },
            "map": {
                "syntax": "map(function, iterable, ...)",
                "parameters": [
                    {"name": "function", "description": "A function to apply to each item of the iterable(s)."},
                    {"name": "iterable", "description": "One or more iterables."}
                ],
                "example": "numbers = [1, 2, 3]\nsquared = list(map(lambda x: x*x, numbers))\nprint(squared) # Output: [1, 4, 9]"
            },
            "max": {
                "syntax": "max(iterable, *[, key, default]) or max(arg1, arg2, *args[, key])",
                "parameters": [
                    {"name": "iterable", "description": "An iterable of values."},
                    {"name": "arg1, arg2, *args", "description": "Two or more positional arguments."},
                    {"name": "key", "description": "Optional. A function to customize the comparison (like `sorted`)."},
                    {"name": "default", "description": "Optional. The value to return if the iterable is empty (only when one iterable is provided)."}
                ],
                "example": "max([1, 5, 2])     # Output: 5\nmax(10, 20, 5)     # Output: 20"
            },
            "min": {
                "syntax": "min(iterable, *[, key, default]) or min(arg1, arg2, *args[, key])",
                "parameters": [
                    {"name": "iterable", "description": "An iterable of values."},
                    {"name": "arg1, arg2, *args", "description": "Two or more positional arguments."},
                    {"name": "key", "description": "Optional. A function to customize the comparison (like `sorted`)."},
                    {"name": "default", "description": "Optional. The value to return if the iterable is empty (only when one iterable is provided)."}
                ],
                "example": "min([1, 5, 2])     # Output: 1\nmin(10, 20, 5)     # Output: 5"
            },
            "next": {
                "syntax": "next(iterator[, default])",
                "parameters": [
                    {"name": "iterator", "description": "An iterator object."},
                    {"name": "default", "description": "Optional. The value to return if the iterator is exhausted."}
                ],
                "example": "it = iter([1, 2])\nprint(next(it)) # Output: 1\nprint(next(it)) # Output: 2\nprint(next(it, 'End')) # Output: End"
            },
            "object": {
                "syntax": "object()",
                "parameters": [],
                "example": "obj = object()\nprint(type(obj)) # Output: <class 'object'>"
            },
            "oct": {
                "syntax": "oct(number)",
                "parameters": [
                    {"name": "number", "description": "An integer."}
                ],
                "example": "oct(8)  # Output: '0o10'"
            },
            "open": {
                "syntax": "open(file, mode='r', encoding=None, ...)",
                "parameters": [
                    {"name": "file", "description": "Path to the file or file descriptor."},
                    {"name": "mode", "description": "Optional. Mode string ('r', 'w', 'a', 'b', 't', '+', etc.)."},
                    {"name": "encoding", "description": "Optional. Encoding for text mode (e.g., 'utf-8')."}
                ],
                "example": "with open('my_file.txt', 'w') as f:\n    f.write('Hello, world!')"
            },
            "ord": {
                "syntax": "ord(c)",
                "parameters": [
                    {"name": "c", "description": "A single Unicode character."}
                ],
                "example": "ord('A')  # Output: 65"
            },
            "pow": {
                "syntax": "pow(base, exp[, mod])",
                "parameters": [
                    {"name": "base", "description": "The base number."},
                    {"name": "exp", "description": "The exponent."},
                    {"name": "mod", "description": "Optional. The modulus (if provided, returns (base**exp) % mod)."}
                ],
                "example": "pow(2, 3)     # Output: 8\npow(2, 3, 3)  # Output: 2 (8 % 3)"
            },
            "print": {
                "syntax": "print(*objects, sep=' ', end='\\n', file=sys.stdout, flush=False)",
                "parameters": [
                    {"name": "objects", "description": "One or more objects to print."},
                    {"name": "sep", "description": "Optional. String inserted between values, default a space."},
                    {"name": "end", "description": "Optional. String appended after the last value, default a newline."},
                    {"name": "file", "description": "Optional. A file-like object (stream) to write to, default sys.stdout."},
                    {"name": "flush", "description": "Optional. If True, the stream is forcibly flushed."}
                ],
                "example": "print('Hello', 'World', sep='-') # Output: Hello-World\nprint('Done.', end='')"
            },
            "property": {
                "syntax": "property(fget=None, fset=None, fdel=None, doc=None)",
                "parameters": [
                    {"name": "fget", "description": "Optional. Function to get an attribute value."},
                    {"name": "fset", "description": "Optional. Function to set an attribute value."},
                    {"name": "fdel", "description": "Optional. Function to delete an attribute value."},
                    {"name": "doc", "description": "Optional. Docstring for the property."}
                ],
                "example": "class C:\n    def __init__(self, x):\n        self._x = x\n    def getx(self):\n        return self._x\n    def setx(self, value):\n        self._x = value\n    x = property(getx, setx)"
            },
            "quit": {
                "syntax": "quit([code=None])",
                "parameters": [
                    {"name": "code", "description": "Optional. An exit status code (default None)."}
                ],
                "example": "import sys\n# quit()\n# quit('Exiting program')\n# Note: Calling quit() directly in some environments (like IDLE) might just raise SystemExit"
            },
            "range": {
                "syntax": "range(stop) or range(start, stop[, step])",
                "parameters": [
                    {"name": "start", "description": "Optional. The starting number of the sequence (inclusive, default 0)."},
                    {"name": "stop", "description": "The ending number of the sequence (exclusive)."},
                    {"name": "step", "description": "Optional. The increment between numbers (default 1)."}
                ],
                "example": "list(range(5))        # Output: [0, 1, 2, 3, 4]\nlist(range(1, 10, 2)) # Output: [1, 3, 5, 7, 9]"
            },
            "repr": {
                "syntax": "repr(object)",
                "parameters": [
                    {"name": "object", "description": "Any object."}
                ],
                "example": "repr('hello')  # Output: \"'hello'\"\nrepr([1, 2])   # Output: '[1, 2]'"
            },
            "reversed": {
                "syntax": "reversed(seq)",
                "parameters": [
                    {"name": "seq", "description": "A sequence object (list, tuple, string) that supports `__len__()` or `__getitem__()`."}
                ],
                "example": "list(reversed([1, 2, 3])) # Output: [3, 2, 1]"
            },
            "round": {
                "syntax": "round(number[, ndigits])",
                "parameters": [
                    {"name": "number", "description": "The number to round."},
                    {"name": "ndigits", "description": "Optional. The number of decimal places to round to. If omitted, rounds to the nearest integer."}
                ],
                "example": "round(3.14159, 2) # Output: 3.14\nround(2.5)        # Output: 2 (rounds to nearest even)"
            },
            "set": {
                "syntax": "set([iterable])",
                "parameters": [
                    {"name": "iterable", "description": "Optional. An iterable from which to initialize the set."}
                ],
                "example": "my_set = set([1, 2, 2, 3])\nprint(my_set) # Output: {1, 2, 3}"
            },
            "setattr": {
                "syntax": "setattr(object, name, value)",
                "parameters": [
                    {"name": "object", "description": "The object to set the attribute on."},
                    {"name": "name", "description": "A string representing the attribute's name."},
                    {"name": "value", "description": "The value to set the attribute to."}
                ],
                "example": "class MyClass:\n    pass\nobj = MyClass()\nsetattr(obj, 'attribute_name', 'some_value')\nprint(obj.attribute_name) # Output: some_value"
            },
            "slice": {
                "syntax": "slice(stop) or slice(start, stop[, step])",
                "parameters": [
                    {"name": "start", "description": "Optional. The starting index (inclusive, default 0)."},
                    {"name": "stop", "description": "The ending index (exclusive)."},
                    {"name": "step", "description": "Optional. The step or increment (default 1)."}
                ],
                "example": "my_list = [1, 2, 3, 4, 5]\ns = slice(1, 4)\nprint(my_list[s]) # Output: [2, 3, 4]"
            },
            "sorted": {
                "syntax": "sorted(iterable, *, key=None, reverse=False)",
                "parameters": [
                    {"name": "iterable", "description": "An iterable to be sorted."},
                    {"name": "key", "description": "Optional. A function to be called on each list element prior to making comparisons."},
                    {"name": "reverse", "description": "Optional. If True, sort in descending order."}
                ],
                "example": "sorted([3, 1, 4]) # Output: [1, 3, 4]\nsorted(['apple', 'Banana'], key=str.lower) # Output: ['Banana', 'apple']"
            },
            "staticmethod": {
                "syntax": "@staticmethod",
                "parameters": [],
                "example": "class MyClass:\n    @staticmethod\n    def my_static_method():\n        return 'This is a static method'"
            },
            "str": {
                "syntax": "str(object='') or str(object, encoding, errors)",
                "parameters": [
                    {"name": "object", "description": "Optional. An object to convert to a string."},
                    {"name": "encoding", "description": "Optional. The encoding of the object if it's bytes."},
                    {"name": "errors", "description": "Optional. How to handle encoding errors."}
                ],
                "example": "str(123)       # Output: '123'\nstr(b'bytes', 'utf-8') # Output: 'bytes'"
            },
            "sum": {
                "syntax": "sum(iterable, start=0)",
                "parameters": [
                    {"name": "iterable", "description": "An iterable of numbers."},
                    {"name": "start", "description": "Optional. An initial value to which the items are added (default 0)."}
                ],
                "example": "sum([1, 2, 3])      # Output: 6\nsum([1, 2, 3], 10)  # Output: 16"
            },
            "super": {
                "syntax": "super([type[, object_or_type]])",
                "parameters": [
                    {"name": "type", "description": "The type of the class that calls `super()`."},
                    {"name": "object_or_type", "description": "An instance of `type` or a subtype of `type`."}
                ],
                "example": "class Parent:\n    def greet(self): return 'Hello from Parent'\nclass Child(Parent):\n    def greet(self):\n        return super().greet() + ' and Child'\nprint(Child().greet()) # Output: Hello from Parent and Child"
            },
            "tuple": {
                "syntax": "tuple([iterable])",
                "parameters": [
                    {"name": "iterable", "description": "Optional. An iterable from which to create the tuple."}
                ],
                "example": "my_tuple = tuple([1, 2, 3])\nprint(my_tuple) # Output: (1, 2, 3)"
            },
            "type": {
                "syntax": "type(object) or type(name, bases, dict)",
                "parameters": [
                    {"name": "object", "description": "The object to get the type of."},
                    {"name": "name", "description": "String representing the class name."},
                    {"name": "bases", "description": "Tuple of base classes."},
                    {"name": "dict", "description": "Dictionary containing the class's namespace."}
                ],
                "example": "type(1) # Output: <class 'int'>\nclass MyClass: pass\nMyClassType = type('MyNewClass', (object,), {'x': 1})\nobj = MyClassType()\nprint(obj.x) # Output: 1"
            },
            "vars": {
                "syntax": "vars([object])",
                "parameters": [
                    {"name": "object", "description": "Optional. An object. If omitted, returns the `__dict__` of the current module."}
                ],
                "example": "class MyClass:\n    def __init__(self):\n        self.x = 1\n        self.y = 2\nobj = MyClass()\nprint(vars(obj)) # Output: {'x': 1, 'y': 2}"
            },
            "zip": {
                "syntax": "zip(*iterables)",
                "parameters": [
                    {"name": "iterables", "description": "One or more iterables."}
                ],
                "example": "list(zip([1, 2], ['a', 'b'])) # Output: [(1, 'a'), (2, 'b')]"
            }
        }
        # End of curated syntax overrides

        # --- Menu Bar Setup ---
        self.menubar = Menu(master)  # Create a menu bar
        master.config(menu=self.menubar)  # Assign the menu bar to the root window

        self.help_menu = Menu(self.menubar, tearoff=0)  # Create a 'Help' menu
        self.menubar.add_cascade(label="Help", menu=self.help_menu)  # Add 'Help' to the menu bar
        self.help_menu.add_command(label="About PyRef", command=self.show_about_dialog)  # Add 'About' command

        # --- Top Control Frame (Search, Navigation, Font Size) ---
        top_controls_frame = tk.Frame(master)  # Frame to hold top-level controls
        top_controls_frame.pack(pady=5, fill=tk.X)  # Pack it at the top with padding

        self.search_entry = tk.Entry(top_controls_frame)  # Input field for search queries
        self.search_entry.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)  # Pack to the left, expands horizontally
        self.search_button = tk.Button(top_controls_frame, text="Search", command=self.search)  # Search button
        self.search_button.pack(side=tk.LEFT, padx=5)

        self.clear_search_button = tk.Button(top_controls_frame, text="Clear Search", command=self.clear_search) # Clear search button
        self.clear_search_button.pack(side=tk.LEFT, padx=5)

        self.back_button = tk.Button(top_controls_frame, text="Back", command=self.go_back)  # Back button for history
        self.back_button.pack(side=tk.LEFT, padx=5)
        self.back_button.config(state=tk.DISABLED)  # Disable initially as there's no history yet

        self.forward_button = tk.Button(top_controls_frame, text="Forward", command=self.go_forward)  # Forward button for history
        self.forward_button.pack(side=tk.LEFT, padx=5)
        self.forward_button.config(state=tk.DISABLED)  # Disable initially

        self.current_font_size = 12  # Default font size
        self.min_font_size = 8      # Minimum allowed font size
        self.max_font_size = 24     # Maximum allowed font size

        self.font_decrease_button = tk.Button(top_controls_frame, text="A-", command=self.decrease_font_size) # Decrease font button
        self.font_decrease_button.pack(side=tk.RIGHT, padx=2)
        self.font_increase_button = tk.Button(top_controls_frame, text="A+", command=self.increase_font_size) # Increase font button
        self.font_increase_button.pack(side=tk.RIGHT, padx=2)

        # --- Main Paned Window (Left/Right Panels) ---
        # A PanedWindow allows the user to resize the left and right panels.
        self.main_paned_window = tk.PanedWindow(master, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        self.main_paned_window.pack(fill=tk.BOTH, expand=True)

        # --- Left Frame (Category Buttons and Listbox) ---
        left_frame = tk.Frame(self.main_paned_window)
        self.main_paned_window.add(left_frame, width=250)  # Add left frame to the paned window with initial width

        # Category selection buttons
        self.standard_button = tk.Button(left_frame, text="STANDARD", command=self.show_standard)
        self.standard_button.pack(fill=tk.X, pady=2)
        self.installed_button = tk.Button(left_frame, text="INSTALLED", command=self.show_installed)
        self.installed_button.pack(fill=tk.X, pady=2)
        self.not_installed_button = tk.Button(left_frame, text="NOT INSTALLED (PyPi)", command=self.show_pypi)
        self.not_installed_button.pack(fill=tk.X, pady=2)

        self.menu_listbox_font = font.Font(family="TkDefaultFont", size=self.current_font_size)

        listbox_frame = tk.Frame(left_frame)  # Frame to hold the listbox and its scrollbar
        listbox_frame.pack(fill=tk.BOTH, expand=True)

        self.menu_listbox = tk.Listbox(listbox_frame, width=30, font=self.menu_listbox_font)  # Listbox to display commands/modules
        self.menu_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Bind the listbox selection event to our handler
        self.menu_listbox.bind('<<ListboxSelect>>', self._handle_listbox_select)

        scrollbar = tk.Scrollbar(listbox_frame, orient="vertical", command=self.menu_listbox.yview) # Scrollbar for the listbox
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.menu_listbox.config(yscrollcommand=scrollbar.set)  # Connect scrollbar to listbox

        # --- Right Frame (Info Display and Notes) ---
        right_frame = tk.Frame(self.main_paned_window)
        self.main_paned_window.add(right_frame)  # Add right frame to the paned window

        info_text_controls_frame = tk.Frame(right_frame)
        info_text_controls_frame.pack(fill=tk.BOTH, expand=True)

        self.info_text_font = font.Font(family="TkDefaultFont", size=self.current_font_size)
        # ScrolledText widget for displaying documentation and user notes.
        # `wrap=tk.WORD` ensures text wraps at word boundaries.
        self.info_text = scrolledtext.ScrolledText(info_text_controls_frame, wrap=tk.WORD, font=self.info_text_font)
        self.info_text.pack(fill=tk.BOTH, expand=True)
        # Bind FocusOut event to save notes automatically when the text widget loses focus.
        self.info_text.bind("<FocusOut>", self.save_user_notes)

        self.save_notes_button = tk.Button(right_frame, text="Save Notes", command=self.save_user_notes) # Manual save notes button
        self.save_notes_button.pack(pady=5)

        # --- Application State Variables ---
        self.current_selected_item = None  # Stores the name of the currently displayed item
        self.current_category = "STANDARD"  # Stores the currently active category (STANDARD, INSTALLED, PYPI, SEARCH)

        self.history = []  # List to store navigation history (tuples of (category, item_name_with_prefix))
        self.history_index = -1  # Current position in the history list

        # --- Status Bar ---
        # Displays messages to the user about current operations or status.
        self.status_bar = tk.Label(master, text="Welcome to PyRef! Initializing...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._configure_tags()  # Setup text tags for syntax highlighting and clickable URLs

        # --- Initial Data Loading and Caching ---
        self.status_bar.config(text="Initializing caches...")
        self.master.update_idletasks()  # Force GUI update to show status message

        # Load standard commands cache or build it if not available/expired.
        self.standard_commands_cache = load_cache(STANDARD_CACHE_FILE, "standard")
        if self.standard_commands_cache is None:
            self.status_bar.config(text="Building standard commands cache (first run, this is fast)...")
            self.master.update_idletasks()
            self.standard_commands_cache = sorted(dir(builtins))  # Get all built-in names
            save_cache(self.standard_commands_cache, STANDARD_CACHE_FILE)
            self.status_bar.config(text="Standard commands cache built.")
        self.standard_commands = self.standard_commands_cache  # Assign to active variable

        # Load installed modules cache and PyPI index cache.
        self.installed_modules_cache = load_cache(INSTALLED_CACHE_FILE, "installed") or {}
        # Corrected variable name from PYPI_INDEX_FILE to PYPI_INDEX_CACHE_FILE
        self.pypi_index_cache = load_cache(PYPI_INDEX_CACHE_FILE, "pypi_index") or []

        # Update installed modules (checks for changes since last run)
        self.update_installed_modules()
        # Fetch PyPI packages if the cache is empty (first run or expired)
        if not self.pypi_index_cache:
            self.fetch_pypi_packages()

        self.show_standard()  # Display standard commands by default on startup
        self.status_bar.config(text="PyRef is ready!")  # Final status message

    def _setup_sys_path(self):
        """Adds standard Python site-packages directories to sys.path.
        
        This ensures that dynamically imported modules (e.g., in INSTALLED category)
        can be found by the interpreter.
        """
        # Add global site-packages directories
        for sp_dir in site.getsitepackages():
            if sp_dir not in sys.path:
                sys.path.append(sp_dir)
        # Add user-specific site-packages directory
        user_site_packages = site.getusersitepackages()
        if user_site_packages not in sys.path:
            sys.path.append(user_site_packages)

    def _configure_tags(self):
        """Configures text tags for syntax highlighting and clickable URLs in the info_text widget.
        
        Tags allow applying specific formatting (e.g., color, underline) to parts of the text.
        """
        self.info_text.tag_config("keyword", foreground="blue")
        self.info_text.tag_config("string", foreground="green")
        self.info_text.tag_config("comment", foreground="gray")
        self.info_text.tag_config("function", foreground="purple")
        self.info_text.tag_config("class", foreground="darkred")
        self.info_text.tag_config("builtin", foreground="darkorange")
        self.info_text.tag_config("number", foreground="darkcyan")
        self.info_text.tag_config("url", foreground="blue", underline=True)
        # Bind a click event to the "url" tag to open the URL in a web browser
        self.info_text.tag_bind("url", "<Button-1>", self._open_url)

    def _apply_syntax_highlighting(self, text_widget: scrolledtext.ScrolledText, content_start_line: str, content_end_line: str):
        """Applies basic Python syntax highlighting to a given text range in a ScrolledText widget.

        Args:
            text_widget (scrolledtext.ScrolledText): The Tkinter ScrolledText widget to highlight.
            content_start_line (str): The starting text index (e.g., "1.0").
            content_end_line (str): The ending text index (e.g., "end-1c").
        """
        # Remove all existing tags from the specified range to clear previous highlighting
        for tag in ["keyword", "string", "comment", "function", "class", "builtin", "number", "url"]:
            text_widget.tag_remove(tag, content_start_line, content_end_line)

        # Define regular expressions for different syntax elements
        keywords = r'\b(False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b'
        builtins_re = r'\b(abs|all|any|ascii|bin|bool|breakpoint|bytearray|bytes|callable|chr|classmethod|compile|complex|delattr|dict|dir|divmod|enumerate|eval|exec|filter|float|format|frozenset|getattr|globals|hasattr|hash|help|hex|id|input|int|isinstance|issubclass|iter|len|list|locals|map|max|memoryview|min|next|object|oct|open|ord|pow|print|property|range|repr|reversed|round|set|setattr|slice|sorted|staticmethod|str|sum|super|tuple|type|vars|zip|__import__)\b'
        strings = r'(\"\"\"[\s\S]*?\"\"\"|\'\'\'[\s\S]*?\'\'\'|\".*?\"|\'.*?\')' # Handles single/double quoted and triple-quoted strings
        comments = r'\#.*$' # Matches comments from '#' to end of line
        numbers = r'\b\d+(\.\d+)?([eE][+-]?\d+)?\b' # Matches integers, floats, scientific notation
        functions_def = r'\bdef\s+([a-zA-Z_]\w*)\s*\(' # Captures function names after 'def'
        classes_def = r'\bclass\s+([a-zA-Z_]\w*)\s*(\(|\:)' # Captures class names after 'class'
        urls_re = r'https?://[^\s<>"]+|www\.[^\s<>"]+' # Matches common URL patterns

        # Get the text content from the specified range for processing
        text_content = text_widget.get(content_start_line, content_end_line)
        lines = text_content.splitlines() # Split content into individual lines
        
        # Determine the starting line number in the widget for correct index calculation
        start_line_num = int(float(content_start_line))
        
        # Iterate through each line and apply highlighting based on regex matches
        for i, line in enumerate(lines):
            current_line_index = f"{start_line_num + i}.0" # Current line's starting index in the widget
            
            # Apply tags for each regex pattern
            for match in re.finditer(keywords, line):
                start = f"{current_line_index}+{match.start()}c"
                end = f"{current_line_index}+{match.end()}c"
                text_widget.tag_add("keyword", start, end)

            for match in re.finditer(builtins_re, line):
                start = f"{current_line_index}+{match.start()}c"
                end = f"{current_line_index}+{match.end()}c"
                text_widget.tag_add("builtin", start, end)

            for match in re.finditer(strings, line):
                start = f"{current_line_index}+{match.start()}c"
                end = f"{current_line_index}+{match.end()}c"
                text_widget.tag_add("string", start, end)

            for match in re.finditer(comments, line):
                start = f"{current_line_index}+{match.start()}c"
                end = f"{current_line_index}+{match.end()}c"
                text_widget.tag_add("comment", start, end)
            
            for match in re.finditer(numbers, line):
                start = f"{current_line_index}+{match.start()}c"
                end = f"{current_line_index}+{match.end()}c"
                text_widget.tag_add("number", start, end)

            # Highlighting for function definitions (only the name)
            for match in re.finditer(functions_def, line):
                name_start = match.start(1)
                name_end = match.end(1)
                start = f"{current_line_index}+{name_start}c"
                end = f"{current_line_index}+{name_end}c"
                text_widget.tag_add("function", start, end)

            # Highlighting for class definitions (only the name)
            for match in re.finditer(classes_def, line):
                name_start = match.start(1)
                name_end = match.end(1)
                start = f"{current_line_index}+{name_start}c"
                end = f"{current_line_index}+{name_end}c"
                text_widget.tag_add("class", start, end)
            
            # Highlighting for URLs
            for match in re.finditer(urls_re, line):
                start = f"{current_line_index}+{match.start()}c"
                end = f"{current_line_index}+{match.end()}c"
                text_widget.tag_add("url", start, end)

    def _open_url(self, event: tk.Event):
        """Event handler for clicking on a URL-tagged text in the info_text widget.

        Args:
            event (tk.Event): The Tkinter event object containing click coordinates.
        """
        # Get the text index at the clicked coordinates
        index = self.info_text.index(f"@{event.x},{event.y}")
        
        # Check if the clicked index has the "url" tag applied
        if "url" in self.info_text.tag_names(index):
            # Get the full text of the line where the click occurred
            line_start_index = self.info_text.index(f"{index} linestart")
            line_end_index = self.info_text.index(f"{index} lineend")
            line_text = self.info_text.get(line_start_index, line_end_index)

            # Find all URLs on that line
            urls_on_line = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', line_text)
            
            # Determine the column of the click within the line
            clicked_column = int(index.split('.')[1])
            
            # Iterate through found URLs to see which one was clicked
            for url in urls_on_line:
                start_match = line_text.find(url)
                end_match = start_match + len(url)
                
                # Check if the click was within the bounds of this URL
                if start_match <= clicked_column < end_match:
                    try:
                        webbrowser.open_new_tab(url)  # Open the URL in the default web browser
                    except Exception as e:
                        messagebox.showerror("Error Opening URL", f"Could not open URL: {url}\nError: {e}")
                    return # Exit after opening the first matching URL

    def _handle_listbox_select(self, event: tk.Event):
        """Handles selection events in the main listbox.

        When a user clicks on an item in the listbox, this function
        identifies the selected item and triggers its information display.

        Args:
            event (tk.Event): The Tkinter event object.
        """
        selected_indices = self.menu_listbox.curselection()  # Get indices of selected items
        if not selected_indices:
            return  # Do nothing if no item is selected

        item_name_with_prefix = self.menu_listbox.get(selected_indices[0])  # Get the text of the selected item

        # Determine the category based on the prefix of the item name
        item_category = self.current_category # Default to current category
        if item_name_with_prefix.startswith("STANDARD: "):
            item_category = "STANDARD"
        elif item_name_with_prefix.startswith("INSTALLED: "):
            item_category = "INSTALLED"
        elif item_name_with_prefix.startswith("NOT INSTALLED (PyPi): "):
            item_category = "PYPI"

        # Manage navigation history. Add to history only if it's a new selection.
        if not self.history or self.history[self.history_index] != (item_category, item_name_with_prefix):
            # If we navigated back and then selected a new item, clear forward history
            if self.history_index < len(self.history) - 1:
                self.history = self.history[:self.history_index + 1]
            self.history.append((item_category, item_name_with_prefix)) # Add new item to history
            self.history_index = len(self.history) - 1 # Update history index

        self._update_history_buttons()  # Enable/disable Back/Forward buttons based on history state
        self.display_info(item_name_with_prefix, item_category) # Display information for the selected item

    def _update_history_buttons(self):
        """Updates the state (enabled/disabled) of the Back and Forward buttons."""
        if self.history_index > 0:
            self.back_button.config(state=tk.NORMAL)  # Enable Back if not at the beginning of history
        else:
            self.back_button.config(state=tk.DISABLED) # Disable Back

        if self.history_index < len(self.history) - 1:
            self.forward_button.config(state=tk.NORMAL) # Enable Forward if not at the end of history
        else:
            self.forward_button.config(state=tk.DISABLED) # Disable Forward

    def go_back(self):
        """Navigates back in the history of viewed items."""
        if self.history_index > 0:
            self.history_index -= 1  # Move back one step in history
            category, item_name_with_prefix = self.history[self.history_index] # Get the item from history
            try:
                # Clear current selection and try to select the item in the listbox
                self.menu_listbox.selection_clear(0, tk.END)
                current_listbox_items = list(self.menu_listbox.get(0, tk.END))
                if item_name_with_prefix in current_listbox_items:
                    idx = current_listbox_items.index(item_name_with_prefix)
                    self.menu_listbox.selection_set(idx) # Select the item
                    self.menu_listbox.see(idx) # Scroll to make it visible
                
                # Display info for the item, explicitly not adding to history to avoid loops
                self.display_info(item_name_with_prefix, category, add_to_history=False)
            except Exception as e:
                self.status_bar.config(text=f"Error going back: Could not re-display '{item_name_with_prefix}'.")
                print(f"Error re-displaying history item: {e}")
                self.history_index += 1 # If error, revert history index
            self._update_history_buttons() # Update button states

    def go_forward(self):
        """Navigates forward in the history of viewed items."""
        if self.history_index < len(self.history) - 1:
            self.history_index += 1 # Move forward one step in history
            category, item_name_with_prefix = self.history[self.history_index] # Get the item from history
            try:
                # Clear current selection and try to select the item in the listbox
                self.menu_listbox.selection_clear(0, tk.END)
                current_listbox_items = list(self.menu_listbox.get(0, tk.END))
                if item_name_with_prefix in current_listbox_items:
                    idx = current_listbox_items.index(item_name_with_prefix)
                    self.menu_listbox.selection_set(idx) # Select the item
                    self.menu_listbox.see(idx) # Scroll to make it visible

                # Display info for the item, explicitly not adding to history to avoid loops
                self.display_info(item_name_with_prefix, category, add_to_history=False)
            except Exception as e:
                self.status_bar.config(text=f"Error going forward: Could not re-display '{item_name_with_prefix}'.")
                print(f"Error re-displaying history item: {e}")
                self.history_index -= 1 # If error, revert history index
            self._update_history_buttons() # Update button states

    def show_standard(self):
        """Displays Python's standard built-in commands in the listbox."""
        self.save_user_notes() # Save any open notes before changing display
        self.menu_listbox.delete(0, tk.END)  # Clear the listbox
        for cmd in self.standard_commands:
            self.menu_listbox.insert(tk.END, cmd) # Insert each standard command
        self.current_category = "STANDARD"  # Set the current category
        self.status_bar.config(text="Showing Standard Python Commands.") # Update status bar
        self.menu_listbox.selection_clear(0, tk.END) # Clear any previous listbox selection

    def update_installed_modules(self):
        """Updates the cache of installed Python modules using `pip freeze`.
        
        This method compares the currently installed packages with the cached list
        and re-inspects modules if changes are detected, or if the cache is expired.
        """
        try:
            self.status_bar.config(text="Checking installed packages (this may take a moment)...")
            self.master.update_idletasks() # Force GUI update
            
            # Run 'pip freeze' to get a list of all installed packages
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'freeze'],
                capture_output=True, text=True, check=True,
                encoding='utf-8', errors='ignore'
            )
            installed_packages_lines = result.stdout.strip().split('\n')
            
            current_installed_names = []
            for line in installed_packages_lines:
                if '==' in line: # Parse package name from 'package==version' format
                    package_name = line.split('==')[0].strip()
                    if package_name:
                        current_installed_names.append(package_name)
            current_installed_names = sorted(list(set(current_installed_names))) # Get unique, sorted names

            cached_package_names = sorted(list(self.installed_modules_cache.keys()))

            # Only re-inspect if the list of installed packages has changed or cache is empty
            if current_installed_names != cached_package_names:
                self.status_bar.config(text="Changes detected! Re-inspecting installed packages... This may take a moment.")
                self.master.update_idletasks()

                new_cache = {}
                # Iterate through current installed packages
                for pkg in current_installed_names:
                    # Skip common build/utility packages that aren't typically documented by users
                    if pkg.lower() in ['pip', 'setuptools', 'wheel', 'distlib', 'filelock', 'platformdirs', 'virtualenv', 'colorama', 'tqdm', 'certifi', 'charset-normalizer', 'idna', 'requests', 'urllib3']:
                        continue
                    # If package is already in cache, reuse its info
                    if pkg in self.installed_modules_cache:
                        new_cache[pkg] = self.installed_modules_cache[pkg]
                    else:
                        # Otherwise, inspect the module to get its functions, classes, etc.
                        new_cache[pkg] = self._get_module_info(pkg)
                    self.status_bar.config(text=f"Inspecting installed: {pkg}...")
                    self.master.update_idletasks()
                self.installed_modules_cache = new_cache # Update the cache
                save_cache(self.installed_modules_cache, INSTALLED_CACHE_FILE) # Save the updated cache to disk
                self.status_bar.config(text="Installed packages cache updated.")
            else:
                self.status_bar.config(text="Installed packages cache is up to date.")

        except FileNotFoundError:
            self.status_bar.config(text="Error: 'pip' command not found. Ensure pip is installed and in your system's PATH.")
            messagebox.showerror("Pip Error", "Error: 'pip' command not found. Ensure pip is installed and in your system's PATH.")
        except subprocess.CalledProcessError as e:
            self.status_bar.config(text=f"Error listing installed packages: {e}")
            messagebox.showerror("Pip Error", f"Error listing installed packages: {e.stderr}")
        except Exception as e:
            self.status_bar.config(text=f"An unexpected error occurred during installed module update: {e}")
            messagebox.showerror("Error", f"An unexpected error occurred during installed module update: {e}")

    def _get_module_info(self, module_name: str):
        """Inspects a Python module to extract its functions, classes, submodules, and docstring.

        Args:
            module_name (str): The name of the module to inspect.

        Returns:
            dict: A dictionary containing 'functions', 'classes', 'modules' lists, and 'doc'.
        """
        info = {"functions": [], "classes": [], "modules": [], "doc": "No module documentation available."}
        try:
            module = importlib.import_module(module_name) # Dynamically import the module
            info["doc"] = inspect.getdoc(module) or "No module documentation available." # Get module-level docstring

            # Iterate through members of the module
            for name, obj in inspect.getmembers(module):
                if name.startswith('_'): # Skip private/special members
                    continue
                # Heuristic to skip very common standard library modules or internal modules
                # that are less likely to be individually looked up by users or lead to excessive inspection
                if hasattr(obj, '__module__') and obj.__module__ and obj.__module__.split('.')[0] in ['tkinter', 'sys', 'os', 'builtins', 'json', 'requests',
                                                     'subprocess', 'inspect', 'site', 'time', 'html', 'collections', 'io',
                                                     'abc', 'typing', 'enum', 'types', 'weakref', 'functools', 'operator',
                                                     'math', 'itertools', 're', 'copy', 'decimal', 'datetime', 'hashlib',
                                                     'random', 'socket', 'threading', 'queue', 'logging', 'warnings',
                                                     'xml', 'html', 'http', 'ssl', 'urllib', 'json', 'uuid', 'zipfile',
                                                     'tarfile', 'shutil', 'tempfile', 'pathlib', 'glob', 'fnmatch',
                                                     'platform', 'getpass', 'mimetypes', 'locale', 'codecs', 'contextlib',
                                                     'asyncio', 'selectors', 'collections.abc', 'struct', 'array', 'binascii',
                                                     'zlib', 'gzip', 'bz2', 'lzma', 'pickle', 'sqlite3', 'csv', 'xml.etree',
                                                     'json.tool', 'venv', 'dis', 'pprint', 'traceback', 'code', 'cmd', 'pdb',
                                                     'profile', 'pstats', 'test', 'unittest', 'doctest', 'test.support',
                                                     'lib2to3', 'distutils', 'setuptools', 'packaging', 'pip', 'wheel']:
                    continue

                # Categorize members
                if inspect.isfunction(obj):
                    info["functions"].append(name)
                elif inspect.isclass(obj):
                    info["classes"].append(name)
                elif inspect.ismodule(obj):
                    info["modules"].append(name)
        except ImportError:
            # Handle modules that cannot be imported (e.g., C extensions, non-importable packages)
            print(f"Could not import {module_name}. It might not be directly importable or is a namespace package.")
            info["doc"] = f"Could not import module '{module_name}'. It might be a namespace package or requires specific import syntax."
        except Exception as e:
            # Catch any other inspection errors
            print(f"Error inspecting {module_name}: {e}")
            info["doc"] = f"Error inspecting module '{module_name}': {e}"
        return info

    def show_installed(self):
        """Displays installed Python modules and their members in the listbox."""
        self.save_user_notes() # Save any open notes
        self.menu_listbox.delete(0, tk.END) # Clear listbox
        display_items = set() # Use a set to store unique items before sorting

        # Add top-level modules and their members to the display list
        for module_name, info in self.installed_modules_cache.items():
            display_items.add(module_name)
            for func in info.get("functions", []):
                display_items.add(f"{module_name}.{func}") # Format as module.function
            for cls in info.get("classes", []):
                display_items.add(f"{module_name}.{cls}") # Format as module.class
            for mod in info.get("modules", []):
                display_items.add(f"{module_name}.{mod}") # Format as module.submodule

        for item in sorted(list(display_items)): # Sort and insert into listbox
            self.menu_listbox.insert(tk.END, item)
        self.current_category = "INSTALLED" # Set current category
        self.status_bar.config(text="Showing Installed Modules.") # Update status bar
        self.menu_listbox.selection_clear(0, tk.END) # Clear any previous selection

    def _fetch_pypi_package_details(self, package_name: str):
        """Fetches detailed information for a PyPI package from PyPI's JSON API.

        Caches the details locally to reduce API calls and enable offline viewing.

        Args:
            package_name (str): The name of the PyPI package.

        Returns:
            dict or None: The package details dictionary if successful, None otherwise.
        """
        # Create a safe filename for caching, replacing problematic characters
        safe_package_name = re.sub(r'[\\/:*?"<>|.]', '_', package_name)
        detail_cache_file = os.path.join(PYPI_DETAIL_CACHE_DIR, f"{safe_package_name}.json")

        cached_data = load_cache(detail_cache_file, "pypi_detail") # Try to load from cache first
        if cached_data:
            return cached_data

        try:
            self.status_bar.config(text=f"Fetching PyPI details for '{package_name}'...")
            self.master.update_idletasks()
            # Make an HTTP GET request to the PyPI JSON API
            response = requests.get(f"https://pypi.org/pypi/{package_name}/json", timeout=5)
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
            data = response.json() # Parse the JSON response
            save_cache(data, detail_cache_file) # Save the fetched data to cache
            self.status_bar.config(text=f"PyPI details for '{package_name}' fetched and cached.")
            return data
        except requests.exceptions.RequestException as e:
            self.status_bar.config(text=f"Error fetching PyPI details for '{package_name}': {e}")
            print(f"Error fetching PyPI details for '{package_name}': {e}")
            return None
        except json.JSONDecodeError:
            self.status_bar.config(text=f"Error decoding JSON for '{package_name}' from PyPI.")
            print(f"Error decoding JSON for '{package_name}' from PyPI.")
            return None
        except Exception as e:
            self.status_bar.config(text=f"An unexpected error fetching PyPI details for '{package_name}': {e}")
            print(f"An unexpected error fetching PyPI details for '{package_name}': {e}")
            return None

    def fetch_pypi_packages(self):
        """Fetches the list of all available packages from PyPI's simple index.
        
        This list is used for the "NOT INSTALLED (PyPI)" category.
        """
        self.status_bar.config(text="Fetching PyPI package index (this might take a moment)...")
        self.master.update_idletasks()

        try:
            # Request the simple HTML index page from PyPI
            response = requests.get("https://pypi.org/simple/", timeout=10)
            response.raise_for_status()

            # --- HTML Parsing for PyPI Index ---
            # A simple HTML parser to extract package links from the PyPI simple index page.
            class PackageListParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.packages = []

                def handle_starttag(self, tag, attrs):
                    # Look for 'a' (anchor) tags which contain package links
                    if tag == 'a':
                        for attr, value in attrs:
                            if attr == 'href':
                                # Check if the href points to a package directory (e.g., /simple/package-name/)
                                if value.startswith('/simple/') and value.endswith('/'):
                                    package_name = value.split('/')[-2] # Extract package name from URL path
                                    self.packages.append(package_name)
                                break # Stop checking attributes for this tag

            parser = PackageListParser()
            parser.feed(response.text) # Feed the HTML content to the parser
            self.pypi_index_cache = sorted(list(set(parser.packages))) # Get unique, sorted package names
            save_cache(self.pypi_index_cache, PYPI_INDEX_CACHE_FILE) # Save the index to cache
            self.status_bar.config(text="PyPI index updated from web.")
            # If the user was viewing the PyPI category, refresh the listbox
            if self.current_category == "PYPI":
                self.show_pypi()
        except requests.exceptions.RequestException as e:
            self.status_bar.config(text=f"Error fetching PyPI index: {e}. Check internet connection.")
            messagebox.showwarning("Network Error", f"Could not fetch PyPI index: {e}. Displaying cached data if available.")
        except Exception as e:
            self.status_bar.config(text=f"An unexpected error occurred during PyPI fetch: {e}")
            messagebox.showerror("Error", f"An unexpected error occurred during PyPI fetch: {e}")

    def show_pypi(self):
        """Displays the list of PyPI packages (not installed) in the listbox."""
        self.save_user_notes() # Save any open notes
        self.menu_listbox.delete(0, tk.END) # Clear listbox
        for package in self.pypi_index_cache:
            self.menu_listbox.insert(tk.END, package) # Insert each package name
        self.current_category = "PYPI" # Set current category
        self.status_bar.config(text=f"Showing {len(self.pypi_index_cache)} PyPI Packages.") # Update status bar
        self.menu_listbox.selection_clear(0, tk.END) # Clear any previous selection

    def display_info(self, raw_selected_item: str, item_category_override: str = None, add_to_history: bool = True):
        """Displays detailed information for a selected item (command, module, or PyPI package).

        This is the core function for showing documentation in the right pane.

        Args:
            raw_selected_item (str): The full string from the listbox (may include prefixes).
            item_category_override (str, optional): Explicitly set the category if known.
                                                  Defaults to None, inferring from prefixes.
            add_to_history (bool, optional): If True, add this display event to navigation history.
                                           Defaults to True. Set to False for back/forward actions.
        """
        # Save user notes if a new item is being displayed and it's not a history navigation event
        if add_to_history and self.current_selected_item and self.current_selected_item != raw_selected_item:
             self.save_user_notes() 

        # Determine the actual item name and its category by stripping prefixes
        item_type = item_category_override if item_category_override else self.current_category
        item_name = raw_selected_item

        if raw_selected_item.startswith("INSTALLED: "):
            item_type = "INSTALLED"
            item_name = raw_selected_item.replace("INSTALLED: ", "")
        elif raw_selected_item.startswith("NOT INSTALLED (PyPi): "):
            item_type = "PYPI"
            item_name = raw_selected_item.replace("NOT INSTALLED (PyPi): ", "")
        elif raw_selected_item.startswith("STANDARD: "):
            item_type = "STANDARD"
            item_name = raw_selected_item.replace("STANDARD: ", "")

        self.info_text.delete(1.0, tk.END) # Clear previous content in the info text area
        self.current_selected_item = item_name # Update the currently selected item

        info_to_display = [] # List to build the display text

        if item_type == "INSTALLED":
            # Handle installed modules and their members (functions, classes, submodules)
            if "." in item_name:
                # This is a member of an installed module (e.g., 'requests.get')
                parts = item_name.split('.', 1) # Split into module and member name
                module_name = parts[0]
                member_name = parts[1]

                try:
                    module = importlib.import_module(module_name) # Import the parent module
                    obj = getattr(module, member_name) # Get the specific member object

                    info_to_display.append(f"Name: {member_name}\n")
                    info_to_display.append(f"Module: {module_name}\n")
                    info_to_display.append(f"Type: {type(obj).__name__}\n")
                    
                    info_to_display.append(f"\nSyntax:\n")
                    try:
                        # Try to get the signature for functions, classes, and methods
                        if inspect.isfunction(obj) or inspect.isclass(obj) or inspect.ismethod(obj):
                            signature = inspect.signature(obj) # Get the function/method signature
                            info_to_display.append(f"  {member_name}{signature}\n\n")
                            
                            # Display parameters if available in the signature
                            if signature.parameters:
                                info_to_display.append("Parameters:\n")
                                for name, param in signature.parameters.items():
                                    param_info = f"  - {name}"
                                    if param.annotation != inspect.Parameter.empty:
                                        # Add type hints, stripping "typing." prefix for brevity
                                        param_info += f": {str(param.annotation).replace('typing.', '')}"
                                    if param.default != inspect.Parameter.empty:
                                        param_info += f" = {repr(param.default)}" # Add default value
                                    info_to_display.append(param_info + "\n")
                                info_to_display.append("\n")
                            else:
                                info_to_display.append("  (No parameters)\n\n")
                        else:
                            info_to_display.append("  (Syntax not directly applicable or easily determined programmatically)\n\n")
                    except ValueError:
                        # This typically happens for C-implemented objects where signature is not exposed
                        info_to_display.append("  (Signature not available for this object)\n\n")

                    docstring = inspect.getdoc(obj) or "No documentation available." # Get object's docstring
                    info_to_display.append(f"Docstring:\n{docstring}\n\n")

                    examples = self.extract_examples_from_docstring(docstring) # Extract examples
                    if examples:
                        info_to_display.append(f"Examples:\n{examples}\n\n")
                    else:
                        info_to_display.append("Examples: (No examples found in docstring)\n\n")

                except (ImportError, AttributeError) as e:
                    # Handle cases where module or member is not found
                    info_to_display.append(f"Error retrieving info for {item_name}: {e}\n")
                    self.status_bar.config(text=f"Error displaying '{item_name}': {e}")
                except Exception as e:
                    # Catch any other unexpected errors during inspection
                    info_to_display.append(f"An unexpected error occurred for {item_name}: {e}\n")
                    self.status_bar.config(text=f"An unexpected error displaying '{item_name}': {e}")
            else:
                # This is a top-level installed module
                module_name = item_name
                try:
                    module = importlib.import_module(module_name)
                    info_to_display.append(f"Module: {module_name} (Installed)\n")
                    info_to_display.append(f"\nDocstring:\n{inspect.getdoc(module) or self.installed_modules_cache.get(module_name, {}).get('doc', 'No documentation available for this module.')}\n\n")
                    info_to_display.append("Members (functions/classes/submodules) can be found by expanding this module in the 'INSTALLED' category or searching for specific members.\n\n")
                except ImportError as e:
                    info_to_display.append(f"Error importing module {module_name}: {e}\n")
                    info_to_display.append(f"This might be a namespace package or requires specific import syntax. Try 'pip install {module_name}'.\n\n")
                    self.status_bar.config(text=f"Error importing '{module_name}': {e}")
                except Exception as e:
                    info_to_display.append(f"An unexpected error occurred for {module_name}: {e}\n")
                    self.status_bar.config(text=f"An unexpected error displaying '{module_name}': {e}")

        elif item_type == "STANDARD":
            # Handle standard built-in Python commands
            try:
                obj = getattr(builtins, item_name) # Get the built-in object from the 'builtins' module
                info_to_display.append(f"Name: {item_name} (Standard Python Command)\n")
                info_to_display.append(f"Type: {type(obj).__name__}\n")
                
                # --- START: Custom Syntax Logic for Built-ins ---
                # Check for a manually curated syntax override first
                if item_name in self._builtin_syntax_override:
                    override_data = self._builtin_syntax_override[item_name]
                    info_to_display.append(f"\nSyntax:\n  {override_data['syntax']}\n\n")
                    if override_data.get("parameters"):
                        info_to_display.append("Parameters:\n")
                        for param in override_data["parameters"]:
                            info_to_display.append(f"  - {param['name']}: {param['description']}\n")
                        info_to_display.append("\n")
                else:
                    # Fallback to inspect.signature() for other built-ins that might work
                    info_to_display.append(f"\nSyntax:\n")
                    try:
                        if inspect.isfunction(obj) or inspect.isclass(obj) or inspect.ismethod(obj):
                            signature = inspect.signature(obj)
                            info_to_display.append(f"  {item_name}{signature}\n\n")

                            if signature.parameters:
                                info_to_display.append("Parameters:\n")
                                for name, param in signature.parameters.items():
                                    param_info = f"  - {name}"
                                    if param.annotation != inspect.Parameter.empty:
                                        param_info += f": {str(param.annotation).replace('typing.', '')}"
                                    if param.default != inspect.Parameter.empty:
                                        param_info += f" = {repr(param.default)}"
                                    info_to_display.append(param_info + "\n")
                                info_to_display.append("\n")
                            else:
                                info_to_display.append("  (No parameters)\n\n")
                        else:
                            info_to_display.append("  (Syntax not directly applicable or easily determined programmatically)\n\n")
                    except ValueError:
                        info_to_display.append("  (Signature not available for this object)\n\n")
                # --- END: Custom Syntax Logic for Built-ins ---

                docstring = inspect.getdoc(obj) or "No documentation available."
                info_to_display.append(f"Docstring:\n{docstring}\n\n")
                
                # Prioritize curated example if available, otherwise extract from docstring
                if item_name in self._builtin_syntax_override and self._builtin_syntax_override[item_name].get("example"):
                    info_to_display.append(f"Examples:\n{self._builtin_syntax_override[item_name]['example']}\n\n")
                else:
                    examples = self.extract_examples_from_docstring(docstring)
                    if examples:
                        info_to_display.append(f"Examples:\n{examples}\n\n")
                    else:
                        info_to_display.append("Examples: (No examples found in docstring)\n\n")
            except AttributeError as e:
                info_to_display.append(f"Error retrieving info for standard command {item_name}: {e}\n")
                self.status_bar.config(text=f"Error displaying '{item_name}': {e}")
            except Exception as e:
                info_to_display.append(f"An unexpected error occurred for standard command {item_name}: {e}\n")
                self.status_bar.config(text=f"An unexpected error displaying '{item_name}': {e}")

        elif item_type == "PYPI":
            # Handle PyPI packages (not locally installed)
            info_to_display.append(f"Package: {item_name} (Available on PyPI)\n")
            pypi_details = self._fetch_pypi_package_details(item_name) # Fetch details from PyPI or cache
            if pypi_details:
                # Display version, summary, homepage, and other project URLs
                info_to_display.append(f"Version: {pypi_details.get('info', {}).get('version', 'N/A')}\n")
                summary = pypi_details.get('info', {}).get('summary', 'No summary available.')
                info_to_display.append(f"Summary:\n{summary}\n\n")
                
                home_page = pypi_details.get('info', {}).get('home_page')
                if home_page:
                    info_to_display.append(f"Homepage: {home_page}\n")
                
                project_urls = pypi_details.get('info', {}).get('project_urls')
                if project_urls:
                    info_to_display.append("Project URLs:\n")
                    for label, url in project_urls.items():
                        info_to_display.append(f"  {label}: {url}\n")
                info_to_display.append("\n")
            else:
                info_to_display.append("(Could not fetch additional PyPI details. Check internet or try again later.)\n\n")

            info_to_display.append(f"To install: pip install {item_name}\n") # Provide installation command
            info_to_display.append(f"More info: https://pypi.org/project/{item_name}/\n\n") # Link to PyPI page
        else:
            # Fallback for unexpected item types or search results that don't fit categories
            info_to_display.append(f"Could not fully determine type for: {raw_selected_item}\n")
            info_to_display.append(f"Attempted to parse as: '{item_name}', Inferred type: '{item_type}'\n\n")
            info_to_display.append("Please select from 'STANDARD', 'INSTALLED', or 'NOT INSTALLED (PyPi)' categories directly if search results are unclear.\n")

        # Insert all gathered information into the info_text widget
        start_index = self.info_text.index(tk.END) # Get the current end index before inserting
        self.info_text.insert(tk.END, "".join(info_to_display))
        end_index = self.info_text.index(tk.END) # Get the new end index after inserting

        self._apply_syntax_highlighting(self.info_text, start_index, end_index) # Apply highlighting

        # Add the "Your Notes" separator and load/display user notes
        notes_section_marker = f"\n{'-'*15} Your Notes {'-'*15}\n"
        self.info_text.insert(tk.END, notes_section_marker)
        
        notes = self.load_user_notes(item_name) # Load notes for the current item
        self.info_text.insert(tk.END, notes)
        
        self.info_text.see("1.0") # Scroll to the top of the info text area
        
        self.status_bar.config(text=f"Displaying info for '{item_name}'.") # Update status bar

    def extract_examples_from_docstring(self, docstring: str):
        """Extracts code examples from a docstring using common patterns.

        Args:
            docstring (str): The docstring text.

        Returns:
            str: A string containing extracted examples, or an empty string if none found.
        """
        if not docstring:
            return ""

        docstring = docstring.replace('\r\n', '\n') # Normalize line endings

        # Define regex patterns to find example sections or code blocks
        patterns = [
            # Pattern 1: Looks for "Examples:", "Usage:", "How to Use:" followed by content
            # and ends before another section header or end of string.
            r"(?is)(?:^|\n\s*)(?:Examples?:|Usage(?:s)?:|How to Use:)\s*\n(.*?)(?=\n\s*(?:Parameters|Returns|Yields|Raises|Attributes|Notes|See Also|References|Warnings|Todo|Example|Usage):|\Z)",
            # Pattern 2: Looks for lines starting with '>>>' (Python interactive session)
            # and captures subsequent indented lines, ending before another section header or end of string.
            r"(?is)(?:^|\n)(>>>.*?(?:\n[^\s>>>].*?)*)(?=\n\s*(?:Parameters|Returns|Yields|Raises|Attributes|Notes|See Also|References|Warnings|Todo|Example|Usage):|\Z)",
        ]

        examples_found = []
        for pattern in patterns:
            for match in re.finditer(pattern, docstring):
                example_text = match.group(1).strip()
                if example_text:
                    examples_found.append(example_text)
        
        # Fallback: Find any indented code blocks (4 spaces or tab) that don't look like reStructuredText directives
        if not examples_found:
            code_block_matches = re.findall(r"(?m)^(\s{4}.+|\t.+|>>>.*(?:\n\s{4}.*)*)", docstring)
            for block in code_block_matches:
                trimmed_block = block.strip()
                # Filter out reStructuredText directives like ".. warning::" or list items like "- item"
                if trimmed_block and not trimmed_block.startswith(('-', '*')) and not trimmed_block.startswith('..'):
                    examples_found.append(trimmed_block)

        # Remove duplicate examples and join them with double newlines
        unique_examples = []
        for ex in examples_found:
            if ex not in unique_examples:
                unique_examples.append(ex)

        return "\n\n".join(unique_examples).strip()

    def load_user_notes(self, item_name: str):
        """Loads user-specific notes for a given item from a text file.

        Notes are stored in a dedicated directory with filenames derived from item names.

        Args:
            item_name (str): The name of the item (e.g., 'abs', 'requests.get', 'numpy').

        Returns:
            str: The content of the notes file, or an empty string if no notes exist or an error occurs.
        """
        safe_item_name = re.sub(r'[\\/:*?"<>|.]', '_', item_name) # Sanitize item name for filename
        notes_filename = f"notes_for_{safe_item_name}.txt"
        notes_file_path = os.path.join(NOTES_DIR, notes_filename)
        
        if os.path.exists(notes_file_path):
            try:
                with open(notes_file_path, 'r', encoding='utf-8') as f:
                    return f.read() # Read and return notes content
            except Exception as e:
                print(f"Error loading notes for {item_name}: {e}")
                self.status_bar.config(text=f"Error: Could not load your notes for '{item_name}'.")
                return f"Error: Could not load your notes for {item_name}.\n"
        return "" # Return empty string if file doesn't exist

    def save_user_notes(self, event=None):
        """Saves the user's notes from the info_text widget to a file.

        Notes are extracted from the text widget based on a predefined marker.
        This function is called automatically when the text widget loses focus or
        manually via the 'Save Notes' button.

        Args:
            event (tk.Event, optional): The Tkinter event object (used for binding). Defaults to None.
        """
        if self.current_selected_item: # Only save if an item is currently selected
            safe_item_name = re.sub(r'[\\/:*?"<>|.]', '_', self.current_selected_item) # Sanitize for filename
            notes_file_path = os.path.join(NOTES_DIR, f"notes_for_{safe_item_name}.txt")
            
            full_text = self.info_text.get("1.0", tk.END) # Get all content from the text widget
            
            notes_section_marker = f"\n{'-'*15} Your Notes {'-'*15}\n"
            # Find the start of the notes section marker
            notes_section_start_index = full_text.find(notes_section_marker)

            notes_text = ""
            if notes_section_start_index != -1:
                # Extract text after the marker (your notes)
                notes_text = full_text[notes_section_start_index + len(notes_section_marker):].strip()
            else:
                # This indicates a problem if the marker is missing
                print(f"ERROR: Notes separator not found for '{self.current_selected_item}'. This indicates a logic error in display_info or an unexpected modification of info_text. Notes might be overwritten.")
                self.status_bar.config(text=f"Error: Notes separator missing for '{self.current_selected_item}'. Notes not saved cleanly.")
            
            try:
                ensure_cache_dir() # Ensure notes directory exists

                with open(notes_file_path, 'w', encoding='utf-8') as f:
                    f.write(notes_text) # Write the extracted notes to file
                self.status_bar.config(text=f"Notes saved for '{self.current_selected_item}'.")
            except Exception as e:
                self.status_bar.config(text=f"Error saving notes for '{self.current_selected_item}': {e}")
                messagebox.showerror("Save Error", f"Could not save notes for '{self.current_selected_item}': {e}")

    def increase_font_size(self):
        """Increases the font size in the text display areas."""
        if self.current_font_size < self.max_font_size:
            self.current_font_size += 1
            self._update_font_size() # Apply the new font size
            self.status_bar.config(text=f"Font size increased to {self.current_font_size}.")

    def decrease_font_size(self):
        """Decreases the font size in the text display areas."""
        if self.current_font_size > self.min_font_size:
            self.current_font_size -= 1
            self._update_font_size() # Apply the new font size
            self.status_bar.config(text=f"Font size decreased to {self.current_font_size}.")

    def _update_font_size(self):
        """Applies the current_font_size to the info_text and menu_listbox widgets."""
        self.info_text_font.config(size=self.current_font_size)
        self.menu_listbox_font.config(size=self.current_font_size)

    def search(self):
        """Performs a search across standard commands, installed modules, and PyPI packages."""
        self.save_user_notes() # Save any active notes before search
        query = self.search_entry.get().lower().strip() # Get search query and normalize it
        
        self.info_text.delete(1.0, tk.END) # Clear info display

        if not query:
            # If search query is empty, provide instructions
            self.status_bar.config(text="Enter a search term in the box above and click 'Search'.")
            self.menu_listbox.delete(0, tk.END)
            self.info_text.insert(tk.END, "Enter a search term in the box above to find Python commands, installed modules, or PyPI packages.\n")
            return

        self.status_bar.config(text=f"Searching for '{query}'...")
        self.master.update_idletasks() # Force GUI update to show status

        search_results_items = []

        # Search in Standard Commands
        for cmd in self.standard_commands:
            if query in cmd.lower():
                search_results_items.append(f"STANDARD: {cmd}")

        # Search in Installed Modules and their members
        for module_name, info in self.installed_modules_cache.items():
            if query in module_name.lower():
                search_results_items.append(f"INSTALLED: {module_name}")
            for name_list in [info.get("functions", []), info.get("classes", []), info.get("modules", [])]:
                for member_name in name_list:
                    if query in member_name.lower() or query in f"{module_name}.{member_name}".lower():
                        search_results_items.append(f"INSTALLED: {module_name}.{member_name}")

        # Search in PyPI packages
        for package in self.pypi_index_cache:
            if query in package.lower():
                search_results_items.append(f"NOT INSTALLED (PyPi): {package}")

        self.menu_listbox.delete(0, tk.END) # Clear listbox for results
        if search_results_items:
            # Display results in the listbox
            for item in sorted(list(set(search_results_items))): # Use set to remove duplicates before sorting
                self.menu_listbox.insert(tk.END, item)
            self.current_category = "SEARCH" # Set category to SEARCH
            self.status_bar.config(text=f"Search complete. {len(search_results_items)} results found for '{query}'. Select an item to view.")
            self.info_text.insert(tk.END, "Search results displayed in the left menu.\n\nSelect an item to view its documentation and your notes.\n")
        else:
            # No results found
            self.menu_listbox.insert(tk.END, "No results found for your search.")
            self.current_category = "EMPTY_SEARCH" # Indicate no results
            self.status_bar.config(text=f"No results found for '{query}'.")
            self.info_text.insert(tk.END, "No items match your search query.\n\nPlease try a different search term or browse categories.\n")
        
        self.info_text.see("1.0") # Scroll to top of info text

    def clear_search(self):
        """Clears the search bar and resets the listbox to the previously active category."""
        self.save_user_notes() # Save any active notes
        
        self.search_entry.delete(0, tk.END) # Clear the search input field
        self.info_text.delete(1.0, tk.END) # Clear the info display area
        self.info_text.insert(tk.END, "Welcome to PyRef! Select a category or search for documentation.\n")
        
        # Restore the listbox content based on the current category
        if self.current_category == "INSTALLED":
            self.show_installed()
        elif self.current_category == "PYPI":
            self.show_pypi()
        else:
            self.show_standard() # Default to standard if category was SEARCH or EMPTY_SEARCH
        self.status_bar.config(text="Search cleared. Displaying default category.")
        self.info_text.see("1.0")

    def show_about_dialog(self):
        """Displays an 'About PyRef' dialog with information about the application."""
        about_text = f"""
        **PyRef: Your Offline Python Reference & Personal Notebook**

        **What is PyRef?**
        PyRef is a lightweight, local desktop application designed to be your quick, offline reference for Python. It provides instant access to documentation for:
        
        1.  **Standard Python Commands:** Built-in functions, types, and constants (e.g., `print()`, `list`, `True`).
        2.  **Installed Python Modules:** Documentation for packages you've installed via `pip` (e.g., `requests`, `numpy`, `pygame`) and their individual functions, classes, and submodules.
        3.  **PyPI Packages (Not Installed):** Information on packages available on the Python Package Index (PyPI), allowing you to discover new tools and see installation commands without leaving the app.

        **Key Features:**
        * **Offline Access:** Once cached, documentation for standard and installed modules is available without an internet connection. PyPI package details are cached for future offline viewing too.
        * **Personal Notes:** Add and save your own notes, reminders, and code snippets directly alongside the documentation for any item. Your notes are saved locally and persist between sessions.
        * **Integrated Search:** Quickly find documentation across all categories (Standard, Installed, PyPI).
        * **Syntax Highlighting:** Docstrings and code examples are enhanced with basic Python syntax highlighting for better readability.
        * **Clickable URLs:** External links (like PyPI project pages or homepages) are clickable, opening directly in your web browser.
        * **History Navigation:** Use the "Back" and "Forward" buttons to easily revisit previously viewed items.
        * **Configurable Font Size:** Adjust the text size to your preference for comfortable reading.
        * **Dynamic UI:** Resizable panels allow you to customize the layout.
        
        **Why PyRef?**
        PyRef aims to provide a fast, focused, and personal documentation experience, reducing the need to constantly switch to web browsers or external documentation sites when you just need a quick lookup or want to jot down a thought related to a specific function.

        **Caching & Data:**
        PyRef intelligently caches data to minimize network requests and maximize offline utility.
        * Standard commands are cached for 30 days.
        * Installed modules are re-indexed weekly to reflect changes from `pip install`/`uninstall`.
        * PyPI index is refreshed daily. Individual PyPI package details are cached for 7 days.
        All cache files and your personal notes are stored in:
        `{CACHE_DIR}` (your home directory's hidden PyRef cache folder).

        **Author:** Andrew Stephens (goldalchemist)
        **Version:** 1.0
        **License:** MIT License

        Thank you for using PyRef!
        """
        messagebox.showinfo("About PyRef", about_text)


# --- Main Application Entry Point ---
if __name__ == "__main__":
    # Create the main Tkinter window
    root = tk.Tk()
    # Instantiate the PythonHelperGUI class, passing the root window
    gui = PythonHelperGUI(root)
    # Start the Tkinter event loop, which keeps the GUI running
    root.mainloop()
