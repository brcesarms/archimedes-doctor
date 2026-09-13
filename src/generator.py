"""
Gerador de testes e prompts de IA utilizando o OpenCode CLI.
Envia scaffolding rigoroso para garantir testes robustos e correções cirúrgicas.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def find_opencode_binary() -> str:
    """Localiza o binário do OpenCode CLI no sistema."""
    bin_path = shutil.which("opencode")
    if bin_path:
        return bin_path

    candidates = [
        Path.home() / ".opencode" / "bin" / "opencode",
        Path.home() / ".local" / "bin" / "opencode",
        Path("/usr/local/bin/opencode"),
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)

    return "opencode"


def generate_tests_for_file(
    source_file: Path,
    test_file: Path,
    repo_root: Path,
    functions_to_test: list[str],
    model: Optional[str] = None,
) -> bool:
    """
    Invoca o OpenCode CLI para gerar testes unitários pytest para o arquivo fonte.
    """
    opencode_bin = find_opencode_binary()
    source_content = source_file.read_text(encoding="utf-8", errors="ignore")
    rel_source = source_file.relative_to(repo_root)
    rel_test = test_file.relative_to(repo_root)

    funcs_str = ", ".join(functions_to_test) if functions_to_test else "todas as funções e classes principais"

    prompt = (
        f"Você é um especialista em testes unitários e QA em Python (pytest).\n"
        f"Sua missão é criar ou atualizar o arquivo de testes unitários: `{rel_test}`\n"
        f"Arquivo de origem a ser testado: `{rel_source}`\n\n"
        f"Funções/métodos prioritários para cobrir: {funcs_str}\n\n"
        f"DIRETRIZES DE QUALIDADE OBRIGATÓRIAS:\n"
        f"1. Utilize estritamente `pytest`.\n"
        f"2. NUNCA crie testes vazios ou tautológicos (como `assert True`). Teste valores reais, tipos de retorno e exceções esperadas.\n"
        f"3. Isole chamadas de rede ou I/O externo com mocks apropriados (`unittest.mock.patch` ou fixtures do pytest).\n"
        f"4. Salve o arquivo de teste diretamente em `{rel_test}` utilizando as ferramentas de escrita de arquivo do OpenCode.\n\n"
        f"Conteúdo atual do arquivo `{rel_source}`:\n```python\n{source_content}\n```"
    )

    cmd = [opencode_bin, "run"]
    if model:
        cmd.extend(["-m", model])
    cmd.append(prompt)

    try:
        subprocess.run(cmd, cwd=repo_root, check=True)
        return test_file.is_file()
    except Exception:
        return False


def request_healing_fix(
    source_file: Path,
    test_file: Path,
    repo_root: Path,
    traceback_snippet: str,
    iteration: int,
    max_iterations: int,
    model: Optional[str] = None,
) -> bool:
    """
    Envia o traceback da falha para o OpenCode CLI diagnosticar e aplicar a auto-correção.
    """
    opencode_bin = find_opencode_binary()
    rel_source = source_file.relative_to(repo_root)
    rel_test = test_file.relative_to(repo_root)

    prompt = (
        f"🚨 DIAGNÓSTICO DE FALHA EM TESTE UNITÁRIO (Ciclo de Auto-Cura {iteration}/{max_iterations})\n\n"
        f"O teste em `{rel_test}` falhou ao testar `{rel_source}`.\n\n"
        f"--- STACK TRACE DA FALHA (pytest) ---\n"
        f"{traceback_snippet}\n"
        f"---------------------------------------\n\n"
        f"INSTRUÇÃO DE CURA:\n"
        f"1. Analise cuidadosamente a causa raiz da falha indicada no traceback acima.\n"
        f"2. Se o teste estiver incorreto (ex.: asserção inválida, mock ausente, tipo incompatível), corrija o arquivo `{rel_test}`.\n"
        f"3. Se a falha evidenciou um bug real no código de `{rel_source}`, corrija o arquivo de origem preservando a lógica de negócio pretendida.\n"
        f"4. Aplique a alteração diretamente nos arquivos usando suas ferramentas do OpenCode para que o pytest passe na próxima execução.\n"
    )

    cmd = [opencode_bin, "run"]
    if model:
        cmd.extend(["-m", model])
    cmd.append(prompt)

    try:
        subprocess.run(cmd, cwd=repo_root, check=True)
        return True
    except Exception:
        return False
