# Build stage: install dependencies into a virtualenv using the -dev variant (has pip and a shell).
FROM cgr.dev/chainguard/python:latest-dev@sha256:3fb87eac4bc040b0ee9e131b5fe5746db593b2e31cd08105ec49aa948eec3888 AS build
# The build stage is discarded, so running it as root is fine; the runtime stage is non-root.
USER root
WORKDIR /app
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
COPY requirements.txt .
# --require-hashes: every package, including transitive ones, must match the SHA-256 recorded in
# requirements.txt, so a tampered or swapped release on PyPI cannot be installed.
RUN pip install --no-cache-dir --require-hashes -r requirements.txt \
    # pip is only needed to build. Removing it drops its vendored libraries (msgpack, setuptools
    # metadata), which Trivy flagged as HIGH even though nothing at runtime uses them.
    && pip uninstall -y pip

# Runtime stage: minimal image with no shell or package manager, runs as non-root (uid 65532).
FROM cgr.dev/chainguard/python:latest@sha256:1961420e5f93bd056d4b0b40eca12cdf01b3ed09177aa4d6ec71fab38cbf158f
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
# The entrypoint is only the interpreter so Kubernetes can run other modules from the same signed
# image (the load generator uses args: ["-m", "app.loadgen"]). CMD is the default: the API.
ENTRYPOINT ["python"]
CMD ["-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
