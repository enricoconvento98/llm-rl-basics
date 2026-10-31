# MLflow tracking server with the Postgres driver (the official image does not include psycopg2).
FROM python:3.12-slim

ARG MLFLOW_VERSION=3.17.2
RUN pip install --no-cache-dir "mlflow==${MLFLOW_VERSION}" "psycopg2-binary==2.9.*" \
    && useradd --create-home --uid 1000 mlflow \
    && mkdir -p /mlartifacts && chown mlflow /mlartifacts

USER mlflow
EXPOSE 5000
