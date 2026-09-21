FROM python:3.11-slim
WORKDIR /app
COPY services/context-composer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY packages /app/packages
COPY services/context-composer /app/services/context-composer
WORKDIR /app/services/context-composer
EXPOSE 8003
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
