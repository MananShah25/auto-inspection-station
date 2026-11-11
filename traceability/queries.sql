-- Yield percentage
SELECT
  ROUND(100.0 * SUM(CASE WHEN result = 'PASS' THEN 1 ELSE 0 END) / COUNT(*), 2) AS yield_percent
FROM units;

-- Reject reasons ranked
SELECT fail_reason, COUNT(*) AS rejects
FROM units
WHERE result = 'FAIL'
GROUP BY fail_reason
ORDER BY rejects DESC, fail_reason;

-- Mean cycle time
SELECT ROUND(AVG(cycle_time_ms), 2) AS mean_cycle_time_ms
FROM units;

-- p95 cycle time
WITH ordered AS (
  SELECT
    cycle_time_ms,
    ROW_NUMBER() OVER (ORDER BY cycle_time_ms) AS rn,
    COUNT(*) OVER () AS total
  FROM units
)
SELECT cycle_time_ms AS p95_cycle_time_ms
FROM ordered
WHERE rn >= CAST(((total * 95) + 99) / 100 AS INTEGER)
ORDER BY rn
LIMIT 1;

-- Throughput per minute
SELECT
  SUBSTR(timestamp_utc, 1, 16) AS minute_utc,
  COUNT(*) AS completed_units
FROM units
GROUP BY minute_utc
ORDER BY minute_utc;
