"""
Module resolver for Nova .nv file imports.

Handles locating, reading, tokenizing, and parsing imported .nv files.
Maintains an import cache to prevent circular and duplicate imports.
"""

import os
from lexer.tokenizer import tokenize
from parser.parser import Parser


class ModuleResolver:
    def __init__(self, base_dir=None, target_arch="x86_64", target_os="windows"):
        self.base_dir = base_dir or os.getcwd()
        self.target_arch = target_arch
        self.target_os = target_os
        self.imported = {}  # module_name -> parsed AST (cache)

    def resolve(self, module_name, importer_dir=None):
        """
        Resolve and parse a .nv module by name.

        Args:
            module_name: The module name (e.g., "math" resolves to "math.nv")
            importer_dir: Directory of the file doing the import (for relative resolution)

        Returns:
            List of AST nodes from the imported module.

        Raises:
            FileNotFoundError: If the module .nv file cannot be found.
        """
        # Return cached result if already imported
        if module_name in self.imported:
            return self.imported[module_name]

        # Mark as being imported (prevents circular imports)
        self.imported[module_name] = []

        # Resolve the file path
        file_path = self._find_module(module_name, importer_dir)
        if file_path is None:
            raise FileNotFoundError(
                f"[Nova Import Error] Module '{module_name}' not found. "
                f"Searched for '{module_name}.nv' in: "
                f"{importer_dir or self.base_dir}"
            )

        # Read, tokenize, and parse the module
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        print(f"[Resolver] Parsing {file_path}")
        tokens = tokenize(source)
        ast = Parser(tokens).parse()

        # Cache the result
        self.imported[module_name] = ast
        return ast

    def _find_module(self, module_name, importer_dir=None):
        """
        Search for a .nv file matching the module name.

        Search order:
            1. Relative to the importing file's directory
            2. Relative to the project base directory
            3. In the stdlib/ directory relative to the Nova installation
        """
        if module_name == "os_impl":
            if self.target_os in ("linux", "macos"):
                module_name = "os_unix"
            else:
                module_name = f"os_{self.target_os}"

        filename = f"{module_name}.nv"

        search_dirs = []

        # 1. Relative to the importing file
        if importer_dir:
            search_dirs.append(importer_dir)

        # 2. Relative to the project base
        search_dirs.append(self.base_dir)

        # 3. stdlib/ directory (relative to Nova's own installation)
        nova_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        stdlib_dir = os.path.join(nova_root, "stdlib")
        search_dirs.append(stdlib_dir)
        
        # 4. Target Architecture specific backend directory
        backend_dir = os.path.join(stdlib_dir, "backend", self.target_arch)
        search_dirs.append(backend_dir)

        for search_dir in search_dirs:
            candidate = os.path.join(search_dir, filename)
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)

        return None

    def get_module_dir(self, module_name, importer_dir=None):
        """Get the directory containing a module (for chained imports)."""
        file_path = self._find_module(module_name, importer_dir)
        if file_path:
            return os.path.dirname(file_path)
        return None
