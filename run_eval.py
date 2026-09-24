import json
import os
from pathlib import Path
from dotenv import load_dotenv
from rich.table import Table
from rich.console import Console
from agent.provider import make_client
from eval.scenarios import SCENARIOS
from improvement.loop import improvement_loop

load_dotenv()
console = Console()


def print_results(title: str, results: list[dict]) -> None:
    table = Table(title=title, show_lines=True)
    table.add_column("Scenario",  style="cyan", no_wrap=True)
    table.add_column("Passed",    justify="center")
    table.add_column("Score",     justify="right")
    for r in results:
        mark = "[green]✓[/green]" if r["passed"] else "[red]✗[/red]"
        table.add_row(r["scenario_id"], mark, f"{r['score']}/{r['max_score']}")
    console.print(table)


def print_comparison(v1: list[dict], v2: list[dict], meta: dict) -> None:
    print_results("[bold]v1 — Before Improvement[/bold]", v1)
    console.print()
    print_results("[bold]v2 — After Improvement[/bold]", v2)
    v1_pass, v2_pass = sum(r["passed"] for r in v1), sum(r["passed"] for r in v2)
    console.print(f"\n[bold]Overall: {v1_pass}/{len(v1)} → {v2_pass}/{len(v2)}[/bold]")
    regressions = meta.get("regressions", [])
    console.print(f"[red]Regressions: {regressions}[/red]" if regressions else "[green]No regressions ✓[/green]")
    patch = meta.get("patch", {})
    if patch.get("root_cause"):
        console.print(f"\n[yellow]Root cause:[/yellow] {patch['root_cause']}")
        console.print(f"[yellow]Section patched:[/yellow] {patch.get('section_to_modify', '')}")


if __name__ == "__main__":
    Path("results").mkdir(exist_ok=True)
    provider = os.getenv("PROVIDER", "groq")
    client   = make_client(provider)
    console.print(f"[bold cyan]Running improvement loop [{provider}]…[/bold cyan]\n")
    v1, v2, meta = improvement_loop(SCENARIOS, "agent/prompts/v1.txt", "agent/prompts/v2.txt", client, provider)
    print_comparison(v1, v2, meta)
    Path("results/run_results.json").write_text(json.dumps({"v1": v1, "v2": v2, "meta": meta}, indent=2, default=str))
    console.print("\n[dim]Full results → results/run_results.json[/dim]")
