from django.core.cache import cache
from django.http import HttpResponse


def throttle(key, limit=5, window=900):
    """Return a 429 response after a small number of attempts in a time window."""
    count = cache.get(key, 0)
    if count >= limit:
        return HttpResponse('Too many attempts. Please try again later.', status=429)
    cache.set(key, count + 1, window)
    return None
