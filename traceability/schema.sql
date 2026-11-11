CREATE TABLE IF NOT EXISTS units (
  serial         INTEGER PRIMARY KEY,
  timestamp_utc TEXT NOT NULL,
  result         TEXT NOT NULL CHECK (result IN ('PASS','FAIL')),
  fail_reason    TEXT,
  cycle_time_ms  INTEGER NOT NULL,
  station_id     TEXT NOT NULL
);
