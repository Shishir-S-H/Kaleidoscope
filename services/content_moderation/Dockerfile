FROM python:3.10-slim

WORKDIR /app

# Copy requirements
COPY services/content_moderation/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY shared /app/shared

# Copy service-specific code
COPY services/content_moderation/ .

CMD ["python", "worker.py"] 