FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 10000
RUN chmod +x /app/scripts/migrate.sh
CMD ["sh", "-c", "/app/scripts/migrate.sh && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
