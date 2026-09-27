# Build stage: install dependencies into a virtualenv using the -dev variant (has pip and a shell).
FROM cgr.dev/chainguard/python:latest-dev@sha256:eb0d45dfc69fecb471d2eaee7a8eea281bf860578ef44cb85db1bfa8165c47fe AS build
# The build stage is discarded, so running it as root is fine; the runtime stage is non-root.
USER root
WORKDIR /app
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    # pip is only needed to build. Removing it drops its vendored libraries (msgpack, setuptools
    # metadata), which Trivy flagged as HIGH even though nothing at runtime uses them.
    && pip uninstall -y pip

# Runtime stage: minimal image with no shell or package manager, runs as non-root (uid 65532).
FROM cgr.dev/chainguard/python:latest@sha256:565af762d7f3efedc4e60d7ac7815e41588211d3f5757be33d8303e915ee6c72
ARG APP_VERSION=dev
LABEL org.opencontainers.image.source="https://github.com/prhoguns/devsecops-supply-chain" \
      org.opencontainers.image.description="demo-api built by the devsecops-supply-chain pipeline" \
      org.opencontainers.image.licenses="MIT"
WORKDIR /app
ENV PATH="/app/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION}
COPY --from=build /app/venv /app/venv
COPY app ./app
USER 65532
EXPOSE 8080
HEALTHCHECK NONE
ENTRYPOINT ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
