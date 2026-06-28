from __future__ import annotations

import ast
import random
from pathlib import Path

_PROTECTED: frozenset[str] = frozenset(
    [
        "int", "str", "float", "bool", "list", "dict", "tuple", "set",
        "None", "True", "False", "Exception", "ValueError", "TypeError",
        "return", "range", "len", "print", "isinstance",
        "pytest", "src", "tests", "Path",
        "annotations", "__future__",
    ]
)

_SYM_FMT = "sym_{:04d}"


def _is_protected(name: str) -> bool:
    if name.startswith("__") or name.endswith("__"):
        return True
    if name.startswith("test_"):
        return True
    return name in _PROTECTED


class _Renamer(ast.NodeTransformer):
    def __init__(self, sym_map: dict[str, str]) -> None:
        self._sym_map = sym_map

    def _map(self, name: str) -> str:
        return self._sym_map.get(name, name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node.name = self._map(node.name)
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        node.name = self._map(node.name)
        self.generic_visit(node)
        return node

    def visit_arg(self, node: ast.arg) -> ast.AST:
        node.arg = self._map(node.arg)
        self.generic_visit(node)
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        node.id = self._map(node.id)
        self.generic_visit(node)
        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        node.attr = self._map(node.attr)
        self.generic_visit(node)
        return node

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.AST:
        if node.module:
            parts = node.module.split(".")
            mapped = [p if p in ("src", "tests") else self._map(p) for p in parts]
            node.module = ".".join(mapped)
        node.names = [self._remap_alias(alias) for alias in node.names]
        self.generic_visit(node)
        return node

    def visit_Import(self, node: ast.Import) -> ast.AST:
        node.names = [self._remap_alias(alias) for alias in node.names]
        self.generic_visit(node)
        return node

    def _remap_alias(self, alias: ast.alias) -> ast.alias:
        alias.name = self._map(alias.name)
        if alias.asname is not None:
            alias.asname = self._map(alias.asname)
        return alias


def _collect_user_names(py_files: list[Path]) -> set[str]:
    names: set[str] = set()
    for path in py_files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not _is_protected(node.name):
                    names.add(node.name)
            elif isinstance(node, ast.arg):
                if not _is_protected(node.arg):
                    names.add(node.arg)
            elif isinstance(node, ast.Name):
                if not _is_protected(node.id):
                    names.add(node.id)
            elif isinstance(node, ast.Attribute):
                if not _is_protected(node.attr):
                    names.add(node.attr)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for part in node.module.split("."):
                        if part not in ("src", "tests") and not _is_protected(part):
                            names.add(part)
                for alias in node.names:
                    if not _is_protected(alias.name):
                        names.add(alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if not _is_protected(alias.name):
                        names.add(alias.name)
    return names


def _build_sym_map(names: set[str], rng: random.Random, clarity: float) -> dict[str, str]:
    ordered = sorted(names)
    rng.shuffle(ordered)
    scramble_count = round(len(ordered) * (1.0 - clarity))
    scramble_count = max(0, min(len(ordered), scramble_count))
    return {name: _SYM_FMT.format(i) for i, name in enumerate(ordered[:scramble_count])}


def _scramble_file(path: Path, sym_map: dict[str, str]) -> None:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except SyntaxError:
        return
    renamer = _Renamer(sym_map)
    new_tree = renamer.visit(tree)
    ast.fix_missing_locations(new_tree)
    new_source = ast.unparse(new_tree)
    path.write_text(new_source, encoding="utf-8")


def _rename_src_files(src_dir: Path, sym_map: dict[str, str]) -> None:
    for py_file in list(src_dir.iterdir()):
        if py_file.name == "__init__.py" or py_file.suffix != ".py":
            continue
        stem = py_file.stem
        new_stem = sym_map.get(stem)
        if new_stem and new_stem != stem:
            py_file.rename(src_dir / f"{new_stem}.py")


class Scrambler:
    def __init__(self, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    def scramble_workspace(self, workspace: Path, clarity: float) -> None:
        if not 0.0 <= clarity <= 1.0:
            raise ValueError(f"clarity must be between 0.0 and 1.0, got {clarity}")
        if clarity >= 1.0:
            return

        py_files = list(workspace.rglob("*.py"))
        names = _collect_user_names(py_files)
        sym_map = _build_sym_map(names, self._rng, clarity)

        for path in py_files:
            _scramble_file(path, sym_map)

        src_dir = workspace / "src"
        if src_dir.is_dir():
            _rename_src_files(src_dir, sym_map)
