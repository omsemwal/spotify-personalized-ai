FROM python:3.11-slim
WORKDIR /app
COPY services/memory-processor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY packages /app/packages
COPY services/memory-processor /app/services/memory-processor
WORKDIR /app/services/memory-processor
EXPOSE 8006
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006"]
