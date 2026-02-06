import os
import time
from fastapi import HTTPException, Request

RATE_LIMIT = {}
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = int(os.getenv('RATE_LIMIT_MAX', '10'))


def _cleanup_timestamps(timestamps):
    cutoff = time.time() - RATE_LIMIT_WINDOW
    return [t for t in timestamps if t >= cutoff]


async def rate_limiter(request: Request):
    """Rate limiter using IP address"""
    key = request.client.host if request.client else 'anonymous'
    timestamps = RATE_LIMIT.get(key, [])
    timestamps = _cleanup_timestamps(timestamps)
    if len(timestamps) >= RATE_LIMIT_MAX:
        msg = f"Rate limit exceeded ({RATE_LIMIT_MAX} req/{RATE_LIMIT_WINDOW}s)"
        raise HTTPException(status_code=429, detail=msg)
    timestamps.append(time.time())
    RATE_LIMIT[key] = timestamps
    return True
