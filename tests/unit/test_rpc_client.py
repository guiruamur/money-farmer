import httpx
import respx

from crypto_farmer.onchain.rpc import RpcClient, RpcError

_URL = "https://base.example/rpc"


@respx.mock
def test_block_number():
    respx.post(_URL).mock(return_value=httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x10"}))
    c = RpcClient(url=_URL)
    assert c.block_number() == 16


@respx.mock
def test_eth_call_returns_hex():
    respx.post(_URL).mock(return_value=httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0xabc"}))
    c = RpcClient(url=_URL)
    assert c.call(to="0xpool", data="0x3850c7bd") == "0xabc"


@respx.mock
def test_get_logs_returns_list():
    logs = [{"data": "0x00", "blockNumber": "0x10"}]
    respx.post(_URL).mock(return_value=httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": logs}))
    c = RpcClient(url=_URL)
    got = c.get_logs(address="0xpool", topics=["0xtopic"], from_block=1, to_block=16)
    assert got == logs


@respx.mock
def test_rpc_error_redacts_url_with_key():
    # The Alchemy URL carries the API key in its path; errors must not leak it.
    respx.post("https://base.example/v2/SECRETKEY").mock(return_value=httpx.Response(400))
    c = RpcClient(url="https://base.example/v2/SECRETKEY")
    try:
        c.block_number()
        assert False, "expected RpcError"
    except RpcError as e:
        assert "SECRETKEY" not in str(e)
        assert "base.example" not in str(e)


@respx.mock
def test_rpc_error_on_error_field():
    respx.post(_URL).mock(return_value=httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "error": {"message": "boom"}}))
    c = RpcClient(url=_URL)
    try:
        c.block_number()
        assert False, "expected RpcError"
    except RpcError:
        pass
