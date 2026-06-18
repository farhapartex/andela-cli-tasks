import grpc
from grpc._utilities import first_version_is_lower

import kv_store_pb2 as kv__store__pb2

GRPC_GENERATED_VERSION = '1.73.0'
GRPC_VERSION = grpc.__version__

if first_version_is_lower(GRPC_VERSION, GRPC_GENERATED_VERSION):
    raise RuntimeError(
        f'The grpc package installed is at version {GRPC_VERSION},'
        + f' but the generated code in kv_store_pb2_grpc.py depends on'
        + f' grpcio>={GRPC_GENERATED_VERSION}.'
        + f' Please upgrade your grpc module to grpcio>={GRPC_GENERATED_VERSION}'
        + f' or downgrade your generated code using grpcio-tools<={GRPC_VERSION}.'
    )


class KVStoreStub(object):
    def __init__(self, channel):
        self.GetVal = channel.unary_unary(
            '/KVStore/GetVal',
            request_serializer=kv__store__pb2.GetValRequest.SerializeToString,
            response_deserializer=kv__store__pb2.GetValResponse.FromString,
            _registered_method=True)
        self.SetVal = channel.unary_unary(
            '/KVStore/SetVal',
            request_serializer=kv__store__pb2.SetValRequest.SerializeToString,
            response_deserializer=kv__store__pb2.SetValResponse.FromString,
            _registered_method=True)


class KVStoreServicer(object):
    def GetVal(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SetVal(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_KVStoreServicer_to_server(servicer, server):
    rpc_method_handlers = {
        'GetVal': grpc.unary_unary_rpc_method_handler(
            servicer.GetVal,
            request_deserializer=kv__store__pb2.GetValRequest.FromString,
            response_serializer=kv__store__pb2.GetValResponse.SerializeToString,
        ),
        'SetVal': grpc.unary_unary_rpc_method_handler(
            servicer.SetVal,
            request_deserializer=kv__store__pb2.SetValRequest.FromString,
            response_serializer=kv__store__pb2.SetValResponse.SerializeToString,
        ),
    }
    generic_handler = grpc.method_handlers_generic_handler('KVStore', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('KVStore', rpc_method_handlers)


class KVStore(object):
    @staticmethod
    def GetVal(request, target, options=(), channel_credentials=None,
               call_credentials=None, insecure=False, compression=None,
               wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(
            request, target, '/KVStore/GetVal',
            kv__store__pb2.GetValRequest.SerializeToString,
            kv__store__pb2.GetValResponse.FromString,
            options, channel_credentials, insecure, call_credentials,
            compression, wait_for_ready, timeout, metadata,
            _registered_method=True)

    @staticmethod
    def SetVal(request, target, options=(), channel_credentials=None,
               call_credentials=None, insecure=False, compression=None,
               wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(
            request, target, '/KVStore/SetVal',
            kv__store__pb2.SetValRequest.SerializeToString,
            kv__store__pb2.SetValResponse.FromString,
            options, channel_credentials, insecure, call_credentials,
            compression, wait_for_ready, timeout, metadata,
            _registered_method=True)
