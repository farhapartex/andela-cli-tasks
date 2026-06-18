#!/bin/bash
set -e

cd /app/kv_store_grpc && python3 server.py &
python3 -m pypiserver run -p 8080 /app/pypi_server/packages/ &

echo "gRPC server started on port 5328"
echo "PyPI server started on port 8080"
echo ""
echo "Run 'docker exec -it <container> bash' to enter the container"

tail -f /dev/null
