"""demo-api: a small HTTP service used to exercise the supply-chain pipeline and the GitOps platform.

It exposes Prometheus metrics and can inject errors on /api/work (ERROR_RATE env var) so the
platform's alerting can be demonstrated by changing one value in Git.
"""

import os
import random
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

APP_VERSION = os.getenv("APP_VERSION", "dev")

REQUESTS = Counter("http_requests_total", "HTTP requests handled", ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "path"])


def error_rate() -> float:
    """Fraction of /api/work requests to fail on purpose (0 to 1). Read from the environment."""
    value = float(os.getenv("ERROR_RATE", "0"))
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"ERROR_RATE must be between 0 and 1, got {value}")
    return value


@asynccontextmanager
async def lifespan(_: FastAPI):
    error_rate()  # fail fast on a bad setting instead of on the first request
    yield


app = FastAPI(title="demo-api", version=APP_VERSION, lifespan=lifespan)


@app.middleware("http")
async def record_metrics(request: Request, call_next):
    # Label by route template, not raw URL, so metric cardinality stays bounded.
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        path = route.path if route else "unmatched"
        if path != "/metrics":
            REQUESTS.labels(request.method, path, str(status)).inc()
            LATENCY.labels(request.method, path).observe(time.perf_counter() - start)


@app.get("/")
def root():
    return {"service": "demo-api", "version": APP_VERSION}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    return {"status": "ready"}


@app.get("/api/work")
def work():
    if random.random() < error_rate():
        raise HTTPException(status_code=503, detail="injected failure")
    return {"result": "done", "version": APP_VERSION}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
