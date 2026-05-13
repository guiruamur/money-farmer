from crypto_farmer.metrics import Metrics


def test_counter_increments():
    m = Metrics()
    m.inc("signals_generated")
    m.inc("signals_generated")
    snap = m.snapshot()
    assert snap["counters"]["signals_generated"] == 2


def test_latency_records_and_aggregates():
    m = Metrics()
    m.record_latency("llm", 100.0)
    m.record_latency("llm", 200.0)
    m.record_latency("llm", 300.0)
    snap = m.snapshot()
    assert snap["latencies"]["llm"]["count"] == 3
    assert snap["latencies"]["llm"]["avg_ms"] == 200.0
    assert snap["latencies"]["llm"]["max_ms"] == 300.0


def test_snapshot_isolated():
    m = Metrics()
    m.inc("x")
    snap = m.snapshot()
    snap["counters"]["x"] = 999  # no afecta al estado interno
    snap2 = m.snapshot()
    assert snap2["counters"]["x"] == 1
