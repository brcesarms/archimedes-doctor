"""
CLI principal do Archimedes Doctor - Gerador Autônomo de Testes com Self-Healing.
"""

import shutil
import sys
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Adiciona src ao path para execução direta
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from scanner import get_git_modified_files, extract_functions_and_classes, locate_or_propose_test_file
from healer import heal_file_tests
from runner import find_python_and_pytest

app = typer.Typer(
    name="archimedes-doctor",
    help="🩺 Archimedes Doctor - Gerador Autônomo de Testes com Loop de Auto-Cura (Self-Healing).",
    add_completion=False,
)
console = Console()


def find_repo_root(start_path: Path) -> Path:
    """Busca a raiz Git do projeto ou retorna o caminho atual."""
    current = start_path.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    return current


@app.command(name="run")
def run_cmd(
    target: Optional[Path] = typer.Argument(
        None,
        help="Arquivo Python ou pasta específica (se omitido, varre arquivos modificados no Git)",
    ),
    all_files: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Varre todos os arquivos Python do projeto, ignorando o git diff",
    ),
    max_retries: int = typer.Option(
        3,
        "--max-retries",
        "-r",
        help="Número máximo de tentativas de auto-cura por arquivo",
    ),
    docker: bool = typer.Option(
        False,
        "--docker",
        help="Força execução dos testes dentro de container Docker (requer docker instalado)",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Modelo de IA a ser repassado ao OpenCode",
    ),
):
    """Executa o ciclo completo de escaneamento, geração de testes e loop de auto-cura."""
    start_dir = Path(".").resolve()
    repo_root = find_repo_root(start_dir)

    console.print(Panel.fit(
        f"[bold cyan]Archimedes Doctor — Centro Médico de Código[/bold cyan] 🩺\n"
        f"📁 [bold]Repositório:[/bold] {repo_root}\n"
        f"🔄 [bold]Máx. Tentativas de Cura:[/bold] {max_retries}\n"
        f"🛡️ [bold]Modo de Isolamento:[/bold] {'Container Docker' if docker else 'Sandbox Local Seguro'}",
        title="🏛️ Archimedes Doctor",
        border_style="cyan"
    ))

    targets: List[Path] = []

    if target:
        resolved = target.resolve()
        if resolved.is_file() and resolved.suffix == ".py":
            targets = [resolved]
        elif resolved.is_dir():
            targets = [f for f in resolved.rglob("*.py") if "tests" not in f.parts and not f.name.startswith("test_")]
        else:
            console.print(f"[bold red]✖ Caminho inválido:[/] {target}")
            raise typer.Exit(code=1)
    elif all_files:
        targets = [f for f in repo_root.rglob("*.py") if "tests" not in f.parts and not f.name.startswith("test_") and not any(p.startswith(".") for p in f.parts)]
    else:
        # Padrão: arquivos modificados no Git
        targets = get_git_modified_files(repo_root)

    if not targets:
        console.print("[green]✔ Nenhum arquivo Python pendente de teste ou modificado encontrado.[/green] ✨")
        return

    console.print(f"[bold yellow]Identificados {len(targets)} arquivo(s) para diagnóstico e tratamento.[/bold yellow]\n")

    results = []
    for f in targets:
        res = heal_file_tests(
            source_file=f,
            repo_root=repo_root,
            max_retries=max_retries,
            use_docker=docker,
            model=model,
        )
        results.append(res)
        console.print("―" * 60)

    # Relatório final
    table = Table(title="📊 Relatório de Diagnóstico & Cura", border_style="cyan")
    table.add_column("Arquivo Fonte", style="white")
    table.add_column("Arquivo de Teste", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Iterações", justify="right")

    for r in results:
        status_style = {
            "passed": "[bold green]Verde (1ª)[/bold green] 🟢",
            "healed": "[bold green]Curado[/bold green] 💚",
            "unhealed": "[bold red]Não Curado[/bold red] ❌",
            "failed": "[bold red]Falha[/bold red] ⚠️",
        }.get(r["status"], r["status"])

        table.add_row(
            Path(r["source"]).name,
            Path(r["test"]).name,
            status_style,
            str(r["iterations"]),
        )

    console.print(table)


@app.command(name="scan")
def scan_cmd(
    target_dir: Path = typer.Argument(Path("."), help="Diretório a ser analisado"),
):
    """Apenas analisa o repositório e lista funções que necessitam de cobertura de testes."""
    repo_root = find_repo_root(target_dir.resolve())
    modified = get_git_modified_files(repo_root)

    table = Table(title="🔍 Arquivos Modificados & Alvos de Teste", border_style="yellow")
    table.add_column("Arquivo", style="bold green")
    table.add_column("Alvos Encontrados", justify="right", style="cyan")
    table.add_column("Arquivo de Teste Previsto", style="dim")

    if not modified:
        console.print("[green]✔ Nenhum arquivo modificado no Git.[/green]")
        return

    for f in modified:
        defs = extract_functions_and_classes(f)
        test_file = locate_or_propose_test_file(f, repo_root)
        table.add_row(
            str(f.relative_to(repo_root)),
            str(len(defs)),
            str(test_file.relative_to(repo_root)),
        )

    console.print(table)


@app.command(name="info")
def info_cmd():
    """Exibe o diagnóstico do ambiente de execução e ferramentas instaladas."""
    start_dir = Path(".").resolve()
    repo_root = find_repo_root(start_dir)
    py_bin, pytest_bin = find_python_and_pytest(repo_root)
    docker_available = shutil.which("docker") is not None

    table = Table(title="🩺 Archimedes Doctor — Status do Ambiente", border_style="cyan")
    table.add_column("Componente", style="bold cyan")
    table.add_column("Valor / Caminho", style="white")

    table.add_row("Repositório Raiz", str(repo_root))
    table.add_row("Python Utilizado", py_bin)
    table.add_row("Pytest Utilizado", pytest_bin)
    table.add_row("Suporte a Docker", "[green]Disponível ✅[/green]" if docker_available else "[yellow]Indisponível (usando Sandbox Local) ⚠️[/yellow]")

    console.print(table)


if __name__ == "__main__":
    app()
