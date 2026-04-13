FROM python:3.11-slim

WORKDIR /app

COPY services/face_matcher/requirements.txt ./services/face_matcher/requirements.txt
COPY shared/requirements.txt ./shared/requirements.txt
RUN pip install --no-cache-dir \
        -r services/face_matcher/requirements.txt \
        -r shared/requirements.txt

COPY shared /app/shared
COPY services/face_matcher /app/services/face_matcher

CMD ["python", "-m", "services.face_matcher.worker"]
