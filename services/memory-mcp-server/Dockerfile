FROM python:3.11-slim
WORKDIR /app
COPY services/memory-mcp-server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY packages /app/packages
COPY services/memory-mcp-server /app/services/memory-mcp-server
WORKDIR /app/services/memory-mcp-server
EXPOSE 8005
CMD ["python", "main.py"]
