"""Rate limiting configuration using slowapi."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.config import get_settings

settings = get_settings()


def client_ip(request: Request) -> str:
    """Real client IP. Every request reaches the backend from the Next.js container, so
    the socket address would put all users in one bucket (5 bad logins/min from anyone
    would lock everyone out). Cloudflare sets CF-Connecting-IP and overwrites any value
    the client sends; Next's proxy adds X-Forwarded-For for direct (LAN) access."""
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return request.headers.get("cf-connecting-ip") or forwarded or get_remote_address(request)


# Create limiter instance with IP-based key function
limiter = Limiter(
    key_func=client_ip,
    default_limits=["1000/minute"] if not settings.debug else ["3000/minute"],
    storage_uri=settings.redis_url,
    strategy="fixed-window",
)


# Rate limit decorators for different endpoint types
AUTH_LIMIT = "5/minute"  # Strict limit for auth endpoints
