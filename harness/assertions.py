from __future__ import annotations

import time
from collections.abc import Mapping

from harness.modbus_client import StateCode, StationClient


def assert_output_state(client: StationClient, expected: Mapping[str, bool]) -> None:
    mismatches = {
        name: {"expected": value, "observed": client.read_coil(name)}
        for name, value in expected.items()
        if client.read_coil(name) != value
    }
    assert not mismatches, f"Output mismatch: {mismatches}"


def assert_state_within(
    client: StationClient,
    expected: StateCode,
    timeout_s: float = 2.0,
    poll_interval_s: float = 0.02,
) -> None:
    deadline = time.monotonic() + timeout_s
    observed = None
    while time.monotonic() < deadline:
        observed = StateCode(client.read_register("STATE_CODE"))
        if observed == expected:
            return
        time.sleep(poll_interval_s)
    raise AssertionError(f"Expected state {expected.name} within {timeout_s}s, observed {observed}")


def assert_timing_between(name: str, observed_ms: int | float, min_ms: int, max_ms: int) -> None:
    assert min_ms <= observed_ms <= max_ms, (
        f"{name} timing out of bounds: expected {min_ms}-{max_ms} ms, observed {observed_ms} ms"
    )


def assert_no_simultaneous_outputs(client: StationClient) -> None:
    extend = client.read_coil("PUSHER_EXTEND")
    retract = client.read_coil("PUSHER_RETRACT")
    assert not (extend and retract), "PUSHER_EXTEND and PUSHER_RETRACT were both energized"


def assert_record_written(rows: list[dict[str, object]], serial: int, result: str) -> None:
    matches = [row for row in rows if row.get("serial") == serial and row.get("result") == result]
    assert len(matches) == 1, f"Expected exactly one {result} record for serial {serial}, found {len(matches)}"

