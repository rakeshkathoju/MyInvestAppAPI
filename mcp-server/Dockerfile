FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8002

# SSE transport when running inside Docker so other containers can reach it
ENV MCP_TRANSPORT=sse
ENV MCP_PORT=8002

CMD ["python", "main.py"]
