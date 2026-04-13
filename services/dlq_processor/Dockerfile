FROM python:3.10-slim

WORKDIR /app

COPY services/dlq_processor/requirements.txt ./services/dlq_processor/requirements.txt
COPY shared/requirements.txt ./shared/requirements.txt
RUN pip install --no-cache-dir \
        -r services/dlq_processor/requirements.txt \
        -r shared/requirements.txt

COPY shared /app/shared
COPY services/dlq_processor/ .

CMD ["python", "worker.py"]
