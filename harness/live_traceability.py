from __future__ import annotations

import argparse
from pathlib import Path

from harness.modbus_client import PymodbusBackend, StationClient
from harness.scenarios import ScenarioContext, run_fail_unit, run_pass_unit, start_station
from traceability.logger import TraceabilityLogger


def main() -> int:
    parser = argparse.ArgumentParser(description="Run and log one live pass and reject cycle")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=1502)
    parser.add_argument("--database", default="traceability/live_traceability.sqlite3")
    args = parser.parse_args()

    client = StationClient(PymodbusBackend(host=args.host, port=args.port))
    logger = TraceabilityLogger(Path(args.database))
    context = ScenarioContext(client=client, logger=logger)
    try:
        start_station(client)
        run_pass_unit(context, 51001)
        run_fail_unit(context, 51002, fail_reason=1)
        print("TOTAL_UNITS=", client.read_register("TOTAL_UNITS"))
        print("TOTAL_REJECTS=", client.read_register("TOTAL_REJECTS"))
        for row in logger.rows():
            print(row)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
