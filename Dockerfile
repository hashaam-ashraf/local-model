FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY local_model ./local_model
RUN pip install --no-cache-dir .

# Run as the host user so the chat log written to the mounted data/ stays editable on the host
ARG UID=1000
ARG GID=1000
RUN groupadd -g "$GID" app && useradd -u "$UID" -g "$GID" -m app \
    && mkdir -p /app/data && chown app:app /app/data
USER app

CMD ["uvicorn", "local_model.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
