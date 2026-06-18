FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN cd pypi_server && \
    python3 -m build && \
    mkdir -p packages && \
    cp dist/vectorops-0.1.0-py3-none-any.whl packages/

RUN chmod +x entrypoint.sh

EXPOSE 5328 8080

ENTRYPOINT ["./entrypoint.sh"]
