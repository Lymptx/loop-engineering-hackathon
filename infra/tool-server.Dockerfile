# MCP JSON-RPC tool server proxied by the optional local Pomerium gateway.
# The offline golden demo does not need this image; USE_POMERIUM=1 does.

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["python", "-m", "sandbox.tool_server"]
