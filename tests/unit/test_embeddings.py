import httpx
import pytest
import respx

from crypto_farmer.learning.embeddings import EmbeddingError, OllamaEmbeddings


@respx.mock
def test_ollama_embed_returns_vector():
    respx.post("http://localhost:11434/api/embeddings").mock(
        return_value=httpx.Response(200, json={"embedding": [0.1, 0.2, 0.3]})
    )
    emb = OllamaEmbeddings(
        base_url="http://localhost:11434", model="nomic-embed-text",
        http_client=httpx.Client(),
    )
    vec = emb.embed("hola mundo")
    assert vec == [0.1, 0.2, 0.3]


@respx.mock
def test_ollama_embed_raises_on_http_error():
    respx.post("http://localhost:11434/api/embeddings").mock(
        return_value=httpx.Response(503)
    )
    emb = OllamaEmbeddings(
        base_url="http://localhost:11434", model="nomic-embed-text",
        http_client=httpx.Client(),
    )
    with pytest.raises(EmbeddingError):
        emb.embed("hola")
