FROM python:3.11-slim

WORKDIR /app

COPY services/profile_enrollment/requirements.txt ./services/profile_enrollment/requirements.txt
COPY shared/requirements.txt ./shared/requirements.txt
RUN pip install --no-cache-dir \
        -r services/profile_enrollment/requirements.txt \
        -r shared/requirements.txt

CMD ["python", "-m", "services.profile_enrollment.worker"]
