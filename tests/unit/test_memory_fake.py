from tests.fakes.memory import InMemoryMemory


def test_fake_memory_search_returns_top_k():
    m = InMemoryMemory()
    m.add(embedding=[1.0, 0.0], text="a", metadata={"pair": "BTC/USDT", "action": "BUY"})
    m.add(embedding=[0.0, 1.0], text="b", metadata={"pair": "ETH/USDT", "action": "SELL"})
    m.add(embedding=[0.9, 0.1], text="c", metadata={"pair": "BTC/USDT", "action": "BUY"})

    hits = m.search(embedding=[1.0, 0.0], k=2)
    assert len(hits) == 2
    assert hits[0].metadata["pair"] == "BTC/USDT"


def test_fake_memory_pair_filter():
    m = InMemoryMemory()
    m.add(embedding=[1.0, 0.0], text="a", metadata={"pair": "BTC/USDT"})
    m.add(embedding=[1.0, 0.0], text="b", metadata={"pair": "ETH/USDT"})
    hits = m.search(embedding=[1.0, 0.0], k=5, pair_filter="ETH/USDT")
    assert len(hits) == 1
    assert hits[0].metadata["pair"] == "ETH/USDT"


def test_fake_memory_update_outcome():
    m = InMemoryMemory()
    eid = m.add(embedding=[1.0], text="x", metadata={"pair": "BTC/USDT"})
    m.update_outcome(entry_id=eid, return_4h=2.0, return_24h=5.0)
    hits = m.search(embedding=[1.0], k=1)
    assert hits[0].metadata["return_4h"] == 2.0
    assert hits[0].metadata["return_24h"] == 5.0


def test_fake_memory_partial_update_outcome():
    """Partial updates: set return_4h first, then return_24h; both must persist."""
    m = InMemoryMemory()
    eid = m.add(embedding=[1.0], text="x", metadata={"pair": "BTC/USDT"})

    # Set only return_4h
    m.update_outcome(entry_id=eid, return_4h=3.5)
    hits = m.search(embedding=[1.0], k=1)
    assert hits[0].metadata["return_4h"] == 3.5
    assert "return_24h" not in hits[0].metadata

    # Set only return_24h — return_4h must still be present
    m.update_outcome(entry_id=eid, return_24h=7.2)
    hits = m.search(embedding=[1.0], k=1)
    assert hits[0].metadata["return_4h"] == 3.5
    assert hits[0].metadata["return_24h"] == 7.2
