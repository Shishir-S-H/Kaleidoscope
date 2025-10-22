FROM python:3.10-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker code
COPY worker.py .

# Shared modules will be mounted as volume from docker-compose.yml

# Run worker
CMD ["python", "worker.py"]

