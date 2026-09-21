FROM python:3.11-slim
WORKDIR /app
COPY services/deletion-orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY packages /app/packages
COPY services/deletion-orchestrator /app/services/deletion-orchestrator
WORKDIR /app/services/deletion-orchestrator
EXPOSE 8004
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
