"""
Modernization Engine — CLI Entry Point
========================================
Usage examples:

  # Modernize a single function to Python
  python main.py modernize --path sample_legacy/ --target calculateInterest --to python

  # Modernize all entry points to Go
  python main.py modernize --path sample_legacy/ --to go --all-entry-points

  # Full project mode: modernize every function/paragraph to Python
  python main.py modernize --path sample_legacy/ --to python --all-units

  # Generate documentation for a COBOL paragraph
  python main.py modernize --path sample_legacy/BILLING.cbl --target CALC-BILLING --to documentation

  # Show dependency graph
  python main.py graph --path sample_legacy/

  # Detect dead code
  python main.py dead-code --path sample_legacy/
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.progress import track

import config
from src.parsers import JavaParser, CobolParser
from src.analysis import DependencyGraph, DeadCodeDetector, ContextOptimizer
from src.llm import GroqClient
from src.output import Modernizer

console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_files(path: str) -> List[str]:
    """Return all supported source files under *path* (file or directory)."""
    p = Path(path)
    if p.is_file():
        return [str(p)]
    files = []
    for ext in config.SUPPORTED_EXTENSIONS:
        files.extend(str(f) for f in p.rglob(f"*{ext}"))
    return files


def _build_graph(files: List[str]) -> DependencyGraph:
    java_parser = JavaParser()
    cobol_parser = CobolParser()
    graph = DependencyGraph()

    for fpath in track(files, description="Parsing files…"):
        ext = Path(fpath).suffix.lower()
        try:
            if ext == ".java":
                result = java_parser.parse_file(fpath)
            else:
                result = cobol_parser.parse_file(fpath)
            graph.add_parse_result(result)
        except Exception as exc:
            console.print(f"[yellow]⚠  {fpath}: {exc}[/yellow]")

    graph.finalize()
    return graph


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

@click.group()
def cli() -> None:
    """⚙️  Modernization Engine — Legacy code → Python / Go / Docs via Groq LLM"""


@cli.command()
@click.option("--path",  "-p", required=True,  help="Source file or directory.")
@click.option("--target","-t", default=None,   help="Function/paragraph name to modernize.")
@click.option("--to",    "-o", default="python",
              type=click.Choice(config.MODERNIZATION_TARGETS, case_sensitive=False),
              help="Target output language.")
@click.option("--all-entry-points", is_flag=True, default=False,
              help="Modernize all detected entry points.")
@click.option("--all-units", is_flag=True, default=False,
              help="Modernize every function/paragraph in the repository (full project mode).")
@click.option("--max-tokens", default=config.MAX_CONTEXT_TOKENS, type=int,
              help="Token budget for context window.")
@click.option("--depth",    default=config.MAX_DEPENDENCY_DEPTH, type=int,
              help="Max dependency depth.")
@click.option("--api-key",  default=config.GROQ_API_KEY, envvar="GROQ_API_KEY",
              help="Groq API key.")
def modernize(
    path: str,
    target: Optional[str],
    to: str,
    all_entry_points: bool,
    all_units: bool,
    max_tokens: int,
    depth: int,
    api_key: str,
) -> None:
    """Modernize legacy code units to Python, Go, or Documentation."""

    files = _collect_files(path)
    if not files:
        console.print(f"[red]No supported files found in: {path}[/red]")
        sys.exit(1)

    mode_label = "ALL UNITS" if all_units else ("ALL ENTRY POINTS" if all_entry_points else to.upper())
    console.print(
        Panel(f"[bold cyan]Modernization Engine[/bold cyan]\n"
              f"Files: {len(files)}  |  Mode: {mode_label}  |  Target lang: {to.upper()}  |  "
              f"Depth: {depth}  |  Budget: {max_tokens} tokens")
    )

    graph = _build_graph(files)
    detector = DeadCodeDetector(graph)
    optimizer = ContextOptimizer(graph, detector, max_tokens=max_tokens, max_depth=depth)

    # Determine what to modernize
    targets: List[str] = []
    if all_units:
        targets = list(graph.get_all_units().keys())
        if not targets:
            console.print("[yellow]No code units found in the parsed files.[/yellow]")
            sys.exit(1)
        console.print(f"[cyan]Full project mode: {len(targets)} units queued.[/cyan]")
    elif all_entry_points:
        targets = graph.get_entry_points()
        if not targets:
            console.print("[yellow]No entry points found. Use --target to specify.[/yellow]")
            sys.exit(1)
    elif target:
        targets = [target]
    else:
        console.print("[red]Specify --target <name>, --all-entry-points, or --all-units.[/red]")
        sys.exit(1)

    llm = GroqClient(api_key=api_key)
    modernizer_engine = Modernizer(groq_client=llm, output_dir=config.OUTPUT_DIR)

    for tgt in targets:
        console.rule(f"[bold green]{tgt}[/bold green]")
        ctx = optimizer.optimize(tgt)

        if ctx is None:
            console.print(f"[red]  Unit '{tgt}' not found in parsed files.[/red]")
            continue

        s = ctx.summary()
        console.print(
            f"  Context: [cyan]{s['total_tokens']}[/cyan] tokens  |  "
            f"Deps: [cyan]{s['dependencies_included']}[/cyan]  |  "
            f"Dead excluded: [yellow]{s['excluded_dead_code']}[/yellow]"
        )

        console.print("  Calling Groq…", end="")
        result = modernizer_engine.run(ctx, target_language=to, save_to_disk=True)
        console.print(" done.")

        if result.success:
            console.print(f"  [green]✅ Saved → {result.output_file}[/green]")
            syntax = Syntax(
                result.modernized_code[:1500]
                + ("\n… (truncated)" if len(result.modernized_code) > 1500 else ""),
                to if to != "documentation" else "markdown",
                theme="monokai",
                line_numbers=True,
            )
            console.print(syntax)
        else:
            console.print(f"  [red]❌ Failed: {result.error}[/red]")


@cli.command()
@click.option("--path", "-p", required=True, help="Source file or directory.")
def graph(path: str) -> None:
    """Display the call dependency graph."""
    files = _collect_files(path)
    dependency_graph = _build_graph(files)

    adj = dependency_graph.to_dict()
    table = Table(title=f"Call Graph — {dependency_graph.summary()}")
    table.add_column("Caller", style="cyan")
    table.add_column("Calls →", style="green")

    for caller, callees in sorted(adj.items()):
        callee_str = ", ".join(callees) if callees else "(none)"
        table.add_row(caller, callee_str)

    console.print(table)


@cli.command("dead-code")
@click.option("--path", "-p", required=True, help="Source file or directory.")
def dead_code(path: str) -> None:
    """Detect dead (unreachable) code units."""
    files = _collect_files(path)
    dependency_graph = _build_graph(files)
    detector = DeadCodeDetector(dependency_graph)
    report = detector.report()

    console.print(Panel(
        f"[bold red]Dead units:[/bold red] {len(report['dead'])}  |  "
        f"[bold green]Live units:[/bold green] {len(report['live'])}"
    ))

    if report["dead"]:
        table = Table(title="☠️  Dead Code (zero callers — excluded from LLM context)")
        table.add_column("Unit", style="red")
        for name in report["dead"]:
            table.add_row(name)
        console.print(table)
    else:
        console.print("[green]✅ No dead code found.[/green]")


@cli.command()
@click.option("--path", "-p", required=True, help="Source file or directory.")
def list_units(path: str) -> None:
    """List all parsed code units."""
    files = _collect_files(path)
    dependency_graph = _build_graph(files)

    table = Table(title=f"Code Units ({dependency_graph.node_count()} found)")
    table.add_column("Unit", style="cyan")
    table.add_column("Language")
    table.add_column("File")
    table.add_column("Lines")
    table.add_column("Entry?")

    for name, unit in sorted(dependency_graph.get_all_units().items()):
        table.add_row(
            unit.qualified_name or name,
            unit.language,
            Path(unit.file_path).name,
            f"{unit.start_line}–{unit.end_line}",
            "✅" if unit.is_entry_point else "",
        )

    console.print(table)


if __name__ == "__main__":
    cli()
