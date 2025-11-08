FROM python:3.10-slim

WORKDIR /app

# Copy requirements
COPY services/es_sync/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY shared /app/shared

# Copy service-specific code
COPY services/es_sync/ .

# Run worker
CMD ["python", "worker.py"]

