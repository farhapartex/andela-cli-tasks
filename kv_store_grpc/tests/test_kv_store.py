import pytest
import grpc
import kv_store_pb2
import kv_store_pb2_grpc


@pytest.fixture(scope="module")
def stub():
    channel = grpc.insecure_channel("localhost:5328")
    return kv_store_pb2_grpc.KVStoreStub(channel)


def test_set_val_returns_stored_value(stub):
    r = stub.SetVal(kv_store_pb2.SetValRequest(key="test_set", value=10))
    assert r.val == 10


def test_get_val_returns_previously_set_value(stub):
    stub.SetVal(kv_store_pb2.SetValRequest(key="test_get", value=55))
    r = stub.GetVal(kv_store_pb2.GetValRequest(key="test_get"))
    assert r.val == 55


def test_get_val_missing_key_returns_zero(stub):
    r = stub.GetVal(kv_store_pb2.GetValRequest(key="nonexistent_key_xyz"))
    assert r.val == 0


def test_overwrite_existing_key(stub):
    stub.SetVal(kv_store_pb2.SetValRequest(key="overwrite_key", value=1))
    stub.SetVal(kv_store_pb2.SetValRequest(key="overwrite_key", value=999))
    r = stub.GetVal(kv_store_pb2.GetValRequest(key="overwrite_key"))
    assert r.val == 999


def test_multiple_keys_are_independent(stub):
    stub.SetVal(kv_store_pb2.SetValRequest(key="key_a", value=1))
    stub.SetVal(kv_store_pb2.SetValRequest(key="key_b", value=2))
    stub.SetVal(kv_store_pb2.SetValRequest(key="key_c", value=3))
    assert stub.GetVal(kv_store_pb2.GetValRequest(key="key_a")).val == 1
    assert stub.GetVal(kv_store_pb2.GetValRequest(key="key_b")).val == 2
    assert stub.GetVal(kv_store_pb2.GetValRequest(key="key_c")).val == 3


def test_negative_value(stub):
    stub.SetVal(kv_store_pb2.SetValRequest(key="neg", value=-42))
    r = stub.GetVal(kv_store_pb2.GetValRequest(key="neg"))
    assert r.val == -42


def test_large_value(stub):
    stub.SetVal(kv_store_pb2.SetValRequest(key="large", value=10**15))
    r = stub.GetVal(kv_store_pb2.GetValRequest(key="large"))
    assert r.val == 10**15


def test_zero_value(stub):
    stub.SetVal(kv_store_pb2.SetValRequest(key="zero", value=0))
    r = stub.GetVal(kv_store_pb2.GetValRequest(key="zero"))
    assert r.val == 0
