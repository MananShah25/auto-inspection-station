from __future__ import annotations

import argparse
import tempfile
import time
from pathlib import Path

from harness.modbus_client import PymodbusBackend, StationClient
from harness.report import ScenarioReport, write_csv, write_markdown
from harness.scenarios import ScenarioContext, all_scenarios
from sim.io_simulator import InMemoryBackend
from traceability.logger import TraceabilityLogger


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PLC inspection station scenarios")
    parser.add_argument("--backend", choices=["sim", "openplc"], default="sim")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=502)
    parser.add_argument("--unit-id", type=int, default=1)
    parser.add_argument("--report", action="store_true", help="Write Markdown and CSV result reports")
    parser.add_argument("--results-md", default="docs/results.md")
    parser.add_argument("--results-csv", default="reports/results.csv")
    args = parser.parse_args()

    results = run_all(args.backend, args.host, args.port, args.unit_id)
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"{status:4} {result.duration_ms:5} ms  {result.name} - {result.detail}")

    if args.report:
        write_markdown(results, Path(args.results_md))
        write_csv(results, Path(args.results_csv))
        print(f"Wrote {args.results_md} and {args.results_csv}")

    return 0 if all(result.passed for result in results) else 1


def run_all(backend_name: str, host: str = "localhost", port: int = 502, unit_id: int = 1) -> list[ScenarioReport]:
    results: list[ScenarioReport] = []
    for scenario in all_scenarios():
        started = time.monotonic()
        try:
            backend = _make_backend(backend_name, host, port, unit_id)
            with tempfile.TemporaryDirectory() as tempdir:
                client = StationClient(backend)
                logger = TraceabilityLogger(Path(tempdir) / "traceability.sqlite3")
                detail = scenario.run(ScenarioContext(client=client, logger=logger))
                client.close()
            results.append(
                ScenarioReport(
                    name=scenario.name,
                    category=scenario.category,
                    passed=True,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    detail=detail,
                )
            )
        except Exception as exc:  # noqa: BLE001 - runner must report scenario failures, not crash early.
            results.append(
                ScenarioReport(
                    name=scenario.name,
                    category=scenario.category,
                    passed=False,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )
    return results


def _make_backend(name: str, host: str, port: int, unit_id: int):
    if name == "sim":
        return InMemoryBackend()
    return PymodbusBackend(host=host, port=port, unit_id=unit_id)


if __name__ == "__main__":
    raise SystemExit(main())

