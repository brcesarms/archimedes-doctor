"""
Scanner de código e repositório Git para o Archimedes Doctor.
Identifica arquivos modificados e extrai funções/classes pendentes de teste via AST.
"""

import ast
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set


def get_git_modified_files(repo_path: Path) -> List[Path]:
    """Retorna a lista de arquivos Python modificados, staged ou não rastreados no repositório."""
    repo_path = repo_path.resolve()
    cmd = ["git", "status", "--porcelain"]
    try:
        res = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, check=True)
    except Exception:
        return []

    modified_files: List[Path] = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # Formato do porcelain: XY filename
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            rel_path = parts[1]
            # Em caso de renomeação "R  old -> new"
            if "->" in rel_path:
                rel_path = rel_path.split("->")[-1].strip()
            full_path = repo_path / rel_path
            if full_path.suffix == ".py" and full_path.is_file():
                if "tests" not in full_path.parts and not full_path.name.startswith("test_"):
                    modified_files.append(full_path)

    return modified_files


def extract_functions_and_classes(file_path: Path) -> List[Dict[str, str]]:
    """Extrai todas as funções e classes de um arquivo Python usando AST."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content)
    except Exception:
        return []

    definitions: List[Dict[str, str]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):  # foca em métodos públicos/principais
                definitions.append({"type": "function", "name": node.name, "lineno": str(node.lineno)})
        elif isinstance(node, ast.ClassDef):
            definitions.append({"type": "class", "name": node.name, "lineno": str(node.lineno)})
            for subnode in node.body:
                if isinstance(subnode, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not subnode.name.startswith("_") or subnode.name == "__init__":
                        definitions.append({
                            "type": "method",
                            "name": f"{node.name}.{subnode.name}",
                            "lineno": str(subnode.lineno),
                        })

    return definitions


def locate_or_propose_test_file(source_file: Path, repo_root: Path) -> Path:
    """Localiza o arquivo de teste correspondente ou define o caminho padrão padronizado."""
    source_name = source_file.stem
    candidates = [
        repo_root / "tests" / f"test_{source_name}.py",
        repo_root / f"test_{source_name}.py",
        source_file.parent / f"test_{source_name}.py",
    ]
    for c in candidates:
        if c.is_file():
            return c

    # Caminho preferencial por convenção
    default_test_dir = repo_root / "tests"
    return default_test_dir / f"test_{source_name}.py"


def get_existing_tests_in_file(test_file: Path) -> Set[str]:
    """Lê um arquivo de teste e retorna os nomes das funções de teste existentes."""
    if not test_file.is_file():
        return set()
    try:
        content = test_file.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content)
        tests = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                tests.add(node.name)
            elif isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        tests.add(sub.name)
        return tests
    except Exception:
        return set()
