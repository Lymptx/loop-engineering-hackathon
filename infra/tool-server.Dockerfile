# Step 6 only — UNTESTED. Builds the MCP tool server that a real Pomerium gateway
# would proxy to (pomerium/docker-compose.yaml references this file). The laptop
# golden demo does NOT use this: it enforces policy in-process via pomerium/ppl.py.
#
# sandbox/tool_server.py is currently a skeleton, not a wired-up MCP server, so this
# image runs but does not yet expose a real MCP endpoint. Finish tool_server.py
# (see its TODO) before relying on this path.

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["python", "-m", "sandbox.tool_server"]
