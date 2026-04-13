FROM python:3.11-slim

WORKDIR /app

COPY services/media_preprocessor/requirements.txt ./services/media_preprocessor/requirements.txt
COPY shared/requirements.txt ./shared/requirements.txt
RUN pip install --no-cache-dir \
        -r services/media_preprocessor/requirements.txt \
        -r shared/requirements.txt

COPY shared /app/shared
COPY services/media_preprocessor /app/services/media_preprocessor

CMD ["python", "-m", "services.media_preprocessor.worker"]
