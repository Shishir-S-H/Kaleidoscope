FROM python:3.11-slim

WORKDIR /app

COPY services/federated_aggregator/requirements.txt ./services/federated_aggregator/requirements.txt
COPY shared/requirements.txt ./shared/requirements.txt
RUN pip install --no-cache-dir \
        -r services/federated_aggregator/requirements.txt \
        -r shared/requirements.txt

CMD ["python", "-m", "services.federated_aggregator.worker"]
