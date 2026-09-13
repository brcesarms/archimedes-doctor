"""
Executor de testes em ambiente isolado (Sandbox Local ou Docker).
Captura o stack trace cirúrgico em caso de falha para realimentar o loop de cura.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional


def find_python_and_pytest(target_dir: Path) -> tuple[str, str]:
    """Descobre o executável python e pytest mais apropriado para o projeto."""
    # 1. Procura no .venv do projeto
    venv_pytest = target_dir / ".venv" / "bin" / "pytest"
    venv_python = target_dir / ".venv" / "bin" / "python"
    if venv_pytest.is_file() and os.access(venv_pytest, os.X_OK):
        return str(venv_python), str(venv_pytest)

    # 2. Procura no PATH
    sys_pytest = shutil.which("pytest")
    sys_python = shutil.which("python3") or "python"
    if sys_pytest:
        return sys_python, sys_pytest

    return sys_python, "pytest"


def run_pytest_isolated(
    test_file: Path,
    repo_root: Path,
    timeout_seconds: int = 45,
    use_docker: bool = False,
) -> Dict[str, Any]:
    """
    Executa o arquivo de teste em ambiente controlado.
    Retorna dicionário com: passed (bool), returncode, stdout, stderr, traceback_snippet.
    """
    if use_docker:
        if shutil.which("docker"):
            return _run_in_docker(test_file, repo_root, timeout_seconds)
        else:
            # Fallback para execução local caso o docker não exista
            pass

    return _run_local_sandbox(test_file, repo_root, timeout_seconds)


def _run_local_sandbox(test_file: Path, repo_root: Path, timeout: int) -> Dict[str, Any]:
    """Execução local em subprocess isolado com timeout de segurança e PYTHONPATH controlado."""
    python_bin, pytest_bin = find_python_and_pytest(repo_root)

    # Prepara ambiente isolado
    env = os.environ.copy()
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{repo_root}:{current_pythonpath}".strip(":")
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    cmd = [pytest_bin, "-v", "--tb=short", str(test_file.resolve())]

    try:
        res = subprocess.run(
            cmd,
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        passed = res.returncode == 0
        traceback_snippet = "" if passed else _extract_surgical_traceback(res.stdout + "\n" + res.stderr)
        return {
            "passed": passed,
            "returncode": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "traceback": traceback_snippet,
            "mode": "local_sandbox",
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Timeout de {timeout}s excedido ao executar o teste.",
            "traceback": f"TimeoutExpired: O teste excedeu o limite seguro de {timeout} segundos (possível loop infinito no código).",
            "mode": "local_sandbox",
        }
    except Exception as e:
        return {
            "passed": False,
            "returncode": 1,
            "stdout": "",
            "stderr": str(e),
            "traceback": f"Erro de execução do ambiente: {e}",
            "mode": "local_sandbox",
        }


def _run_in_docker(test_file: Path, repo_root: Path, timeout: int) -> Dict[str, Any]:
    """Executa o teste montando o repositório como volume em container Docker efêmero."""
    rel_test = test_file.relative_to(repo_root)
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{repo_root}:/workspace",
        "-w", "/workspace",
        "-e", "PYTHONPATH=/workspace",
        "python:3.12-slim",
        "bash", "-c", f"pip install --no-cache-dir pytest >/dev/null 2>&1 && pytest -v --tb=short {rel_test}",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 30)
        passed = res.returncode == 0
        traceback_snippet = "" if passed else _extract_surgical_traceback(res.stdout + "\n" + res.stderr)
        return {
            "passed": passed,
            "returncode": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "traceback": traceback_snippet,
            "mode": "docker",
        }
    except Exception as e:
        return {
            "passed": False,
            "returncode": 1,
            "stdout": "",
            "stderr": str(e),
            "traceback": f"Erro na execução Docker: {e}",
            "mode": "docker",
        }


def _extract_surgical_traceback(output: str) -> str:
    """Extrai apenas os trechos de falha relevantes e linhas de erro do pytest."""
    lines = output.splitlines()
    capturing = False
    relevant_lines = []

    for line in lines:
        if "FAILURES" in line or "ERRORS" in line or line.startswith("FAILED "):
            capturing = True
        if capturing:
            relevant_lines.append(line)
        if "=== short test summary info ===" in line:
            capturing = True

    # Se não conseguiu filtrar, pega as últimas 40 linhas
    if not relevant_lines:
        relevant_lines = lines[-40:]

    return "\n".join(relevant_lines[-60:])
