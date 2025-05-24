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

        **Author:** The PyRef Developer
        **Version:** 1.0
        **License:** MIT License

        Thank you for using PyRef!
