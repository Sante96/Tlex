"""Prometheus metrics for TLEX monitoring."""

from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# Request metrics
REQUEST_COUNT = Counter(
    "tlex_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "tlex_request_latency_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Worker metrics
WORKERS_TOTAL = Gauge(
    "tlex_workers_total",
    "Total number of workers",
)

WORKERS_ACTIVE = Gauge(
    "tlex_workers_active",
    "Number of active workers",
)

WORKERS_FLOOD_WAIT = Gauge(
    "tlex_workers_flood_wait",
    "Number of workers in FloodWait",
)

# Stream metrics
ACTIVE_STREAMS = Gauge(
    "tlex_active_streams",
    "Number of active streams",
)

STREAM_BYTES_TOTAL = Counter(
    "tlex_stream_bytes_total",
    "Total bytes streamed",
)

# Media metrics
MEDIA_ITEMS_TOTAL = Gauge(
    "tlex_media_items_total",
    "Total number of media items",
    ["media_type"],
)

# Cache metrics
CACHE_HITS = Counter(
    "tlex_cache_hits_total",
    "Cache hits",
    ["cache_type"],
)

CACHE_MISSES = Counter(
    "tlex_cache_misses_total",
    "Cache misses",
    ["cache_type"],
)


def get_metrics_response() -> Response:
    """Generate Prometheus metrics response."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
