from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScenarioReport:
    name: str
    category: str
    passed: bool
    duration_ms: int
    detail: str = ""


def write_markdown(results: list[ScenarioReport], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for result in results if result.passed)
    lines = [
        "# Harness Results",
        "",
        "These results are generated from an actual harness run.",
        "",
        f"- Total scenarios: {len(results)}",
        f"- Passed: {passed}",
        f"- Failed: {len(results) - passed}",
        "",
        "| Scenario | Category | Result | Duration ms | Detail |",
        "|---|---|---:|---:|---|",
    ]
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        detail = result.detail.replace("|", "\\|")
        lines.append(f"| {result.name} | {result.category} | {status} | {result.duration_ms} | {detail} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(results: list[ScenarioReport], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["name", "category", "passed", "duration_ms", "detail"])
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "name": result.name,
                    "category": result.category,
                    "passed": result.passed,
                    "duration_ms": result.duration_ms,
                    "detail": result.detail,
                }
            )

