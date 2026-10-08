from functools import wraps

from django.conf import settings
from django.http import HttpResponseNotFound


def feature_disabled(name):
    """Return a clear 404 for routes belonging to disabled product modules."""
    return not getattr(settings, name, False)


def require_feature(setting_name, feature_label):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if feature_disabled(setting_name):
                return HttpResponseNotFound(f'{feature_label} is not enabled in the core product.')
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
