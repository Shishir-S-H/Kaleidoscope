FROM python:3.11-slim

WORKDIR /app

COPY services/media_preprocessor/requirements.txt ./services/media_preprocessor/requirements.txt
COPY shared/requirements.txt ./shared/requirements.txt
RUN pip install --no-cache-dir \
        -r services/media_preprocessor/requirements.txt \
        -r shared/requirements.txt

CMD ["python", "-m", "services.media_preprocessor.worker"]
