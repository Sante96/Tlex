"""Rate limiting configuration using slowapi."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

settings = get_settings()

# Create limiter instance with IP-based key function
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"] if not settings.debug else ["1000/minute"],
    storage_uri=settings.redis_url,
    strategy="fixed-window",
)


# Rate limit decorators for different endpoint types
AUTH_LIMIT = "5/minute"  # Strict limit for auth endpoints
API_LIMIT = "60/minute"  # Standard API limit
STREAM_LIMIT = "30/minute"  # Streaming endpoints
