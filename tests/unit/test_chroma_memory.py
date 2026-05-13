import pytest

from crypto_farmer.learning.memory import ChromaMemory


def test_chroma_memory_roundtrip(tmp_path):
    pytest.importorskip("chromadb")
    m = ChromaMemory(persist_dir=str(tmp_path / "chroma"), collection_name="situations")
    eid = m.add(
        embedding=[0.1, 0.2, 0.3],
        text="situación BTC sobreventa",
        metadata={"pair": "BTC/USDT", "action": "BUY", "timestamp": "2026-05-12T10:00:00Z"},
    )
    assert eid

    hits = m.search(embedding=[0.1, 0.2, 0.3], k=1)
    assert len(hits) == 1
    assert hits[0].metadata["pair"] == "BTC/USDT"

    m.update_outcome(entry_id=eid, return_4h=2.1, return_24h=5.0)
    hits = m.search(embedding=[0.1, 0.2, 0.3], k=1)
    assert hits[0].metadata.get("return_4h") == 2.1


def test_chroma_memory_partial_update_outcome(tmp_path):
    """Partial updates: each horizon can be set independently."""
    pytest.importorskip("chromadb")
    m = ChromaMemory(persist_dir=str(tmp_path / "chroma"), collection_name="situations")
    eid = m.add(
        embedding=[0.1, 0.2, 0.3],
        text="situación BTC sobreventa",
        metadata={"pair": "BTC/USDT", "action": "BUY", "timestamp": "2026-05-12T10:00:00Z"},
    )

    # Set only return_4h
    m.update_outcome(entry_id=eid, return_4h=1.5)
    hits = m.search(embedding=[0.1, 0.2, 0.3], k=1)
    assert hits[0].metadata.get("return_4h") == 1.5
    assert "return_24h" not in hits[0].metadata

    # Set only return_24h — return_4h must persist
    m.update_outcome(entry_id=eid, return_24h=4.0)
    hits = m.search(embedding=[0.1, 0.2, 0.3], k=1)
    assert hits[0].metadata.get("return_4h") == 1.5
    assert hits[0].metadata.get("return_24h") == 4.0
