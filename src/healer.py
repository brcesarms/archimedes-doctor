"""
Orquestrador do ciclo de vida de Auto-Cura (Self-Healing Loop) do Archimedes Doctor.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional

from rich.console import Console
from rich.panel import Panel

# Garante que o diretório src esteja no sys.path para resolução interna
_src_dir = str(Path(__file__).parent.resolve())
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from scanner import (
    locate_or_propose_test_file,
    extract_functions_and_classes,
    get_existing_tests_in_file,
)
from runner import run_pytest_isolated
from generator import generate_tests_for_file, request_healing_fix

console = Console()


def heal_file_tests(
    source_file: Path,
    repo_root: Path,
    max_retries: int = 3,
    use_docker: bool = False,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executa o fluxo completo: gera testes se necessário, executa e itera no loop de auto-cura até passar.
    """
    source_file = source_file.resolve()
    repo_root = repo_root.resolve()
    test_file = locate_or_propose_test_file(source_file, repo_root)

    # 1. Identifica funções e classes
    definitions = extract_functions_and_classes(source_file)
    existing_tests = get_existing_tests_in_file(test_file)

    console.print(f"[bold cyan]🔍 Analisando:[/] {source_file.relative_to(repo_root)} ({len(definitions)} alvos)")

    # Se o arquivo de teste não existir ou estiver vazio, gera os testes iniciais
    if not test_file.is_file() or len(existing_tests) == 0:
        console.print(f"[yellow]📝 Gerando testes iniciais em {test_file.relative_to(repo_root)}...[/yellow]")
        funcs_to_test = [d["name"] for d in definitions]
        success = generate_tests_for_file(source_file, test_file, repo_root, funcs_to_test, model=model)
        if not success or not test_file.is_file():
            return {
                "source": str(source_file),
                "test": str(test_file),
                "status": "failed",
                "iterations": 0,
                "message": "Falha ao gerar arquivo inicial de testes com o OpenCode.",
            }

    # 2. Executa primeira rodada de testes
    console.print(f"[dim cyan]🧪 Executando suite com pytest ({'Docker' if use_docker else 'Sandbox Local'})...[/dim cyan]")
    test_result = run_pytest_isolated(test_file, repo_root, use_docker=use_docker)

    if test_result["passed"]:
        console.print(f"[bold green]✔ Todos os testes passaram na 1ª tentativa![/] 🟢")
        return {
            "source": str(source_file),
            "test": str(test_file),
            "status": "passed",
            "iterations": 1,
            "message": "Sucesso imediato sem necessidade de cura.",
        }

    # 3. Loop de Auto-Cura (Self-Healing Loop)
    console.print(f"[bold red]✖ Testes falharam.[/bold red] Iniciando ciclo de auto-cura ([bold yellow]máx: {max_retries}[/bold yellow])... 🩺")

    iteration = 1
    while iteration <= max_retries:
        console.print(Panel.fit(
            f"[bold yellow]🩹 Ciclo de Auto-Cura {iteration}/{max_retries}[/bold yellow]\n"
            f"Arquivo Alvo: {source_file.name} ➔ Teste: {test_file.name}",
            title="🩺 Archimedes Doctor",
            border_style="yellow"
        ))

        # Envia stack trace para o OpenCode corrigir
        fix_applied = request_healing_fix(
            source_file=source_file,
            test_file=test_file,
            repo_root=repo_root,
            traceback_snippet=test_result["traceback"],
            iteration=iteration,
            max_iterations=max_retries,
            model=model,
        )

        if not fix_applied:
            console.print(f"[red]✖ Falha ao comunicar com OpenCode na iteração {iteration}.[/red]")

        # Reexecuta o teste após a intervenção da IA
        console.print(f"[dim cyan]🔄 Reexecutando testes após intervenção médica...[/dim cyan]")
        test_result = run_pytest_isolated(test_file, repo_root, use_docker=use_docker)

        if test_result["passed"]:
            console.print(f"[bold green]🎉 PACIENTE CURADO! Todos os testes passaram na iteração {iteration}![/] 💚")
            return {
                "source": str(source_file),
                "test": str(test_file),
                "status": "healed",
                "iterations": iteration,
                "message": f"Curado com sucesso na iteração {iteration}.",
            }

        iteration += 1

    console.print(f"[bold red]❌ Limite de {max_retries} iterações atingido sem sucesso total.[/bold red] ⚠️")
    return {
        "source": str(source_file),
        "test": str(test_file),
        "status": "unhealed",
        "iterations": max_retries,
        "last_traceback": test_result["traceback"],
        "message": f"Não foi possível curar completamente após {max_retries} tentativas.",
    }
