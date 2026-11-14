FROM python:3.12.16-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.lock ./
RUN python -m pip install --disable-pip-version-check -r requirements.lock && useradd --uid 10001 --create-home lab
COPY --chown=10001:10001 p091/ ./p091/
COPY --chown=10001:10001 apps/web/ ./apps/web/
COPY --chown=10001:10001 fixtures/ ./fixtures/
COPY --chown=10001:10001 infra/postgres/ ./infra/postgres/
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "p091.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
