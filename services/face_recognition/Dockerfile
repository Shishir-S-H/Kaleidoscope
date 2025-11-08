FROM python:3.10-slim

WORKDIR /app

# Copy requirements
COPY services/face_recognition/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY shared /app/shared

# Copy service-specific code
COPY services/face_recognition/ .

CMD ["python", "worker.py"]
