FROM python:3.11-slim
WORKDIR /app
COPY services/ingestion-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY packages/contracts /app/packages/contracts
COPY packages/pathutil /app/packages/pathutil
COPY services/ingestion-api /app/services/ingestion-api
WORKDIR /app/services/ingestion-api
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
