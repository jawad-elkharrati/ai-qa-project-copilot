ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp

RUN groupadd --gid 10001 copilote \
    && useradd --uid 10001 --gid copilote --no-log-init --create-home copilote

WORKDIR /app

COPY --chown=copilote:copilote . /app

RUN python -m pip install --upgrade pip \
    && python -m pip install . \
    && sed -i 's/\r$//' /app/docker/api-entrypoint.sh \
    && chmod 0555 /app/docker/api-entrypoint.sh \
    && mkdir -p /data \
    && chown copilote:copilote /data

USER 10001:10001

EXPOSE 8000 8501

ENTRYPOINT []

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
