from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from harness.modbus_client import ResultCode, StationClient


FAIL_REASONS = {
    0: None,
    1: "vision_defect",
    2: "dimension",
    3: "barcode",
    4: "timeout_test",
}


@dataclass
class TraceabilityLogger:
    db_path: Path
    station_id: str = "AIS-001"
    last_total_units: int = 0

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(schema)

    def poll(self, client: StationClient) -> bool:
        total_units = client.read_register("TOTAL_UNITS")
        if total_units <= self.last_total_units:
            return False

        serial = client.read_register("LAST_SERIAL")
        result_code = ResultCode(client.read_register("LAST_RESULT"))
        fail_reason_code = client.read_register("LAST_FAIL_REASON")
        cycle_time_ms = client.read_register("LAST_CYCLE_TIME_MS")
        result = "PASS" if result_code == ResultCode.PASS else "FAIL"
        fail_reason = FAIL_REASONS.get(fail_reason_code, f"reason_{fail_reason_code}") if result == "FAIL" else None

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO units
                    (serial, timestamp_utc, result, fail_reason, cycle_time_ms, station_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    serial,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    result,
                    fail_reason,
                    cycle_time_ms,
                    self.station_id,
                ),
            )
        self.last_total_units = total_units
        return True

    def rows(self) -> list[dict[str, object]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute("SELECT * FROM units ORDER BY serial")]

    def counts(self) -> tuple[int, int]:
        with sqlite3.connect(self.db_path) as conn:
            units = conn.execute("SELECT COUNT(*) FROM units").fetchone()[0]
            rejects = conn.execute("SELECT COUNT(*) FROM units WHERE result = 'FAIL'").fetchone()[0]
        return int(units), int(rejects)
