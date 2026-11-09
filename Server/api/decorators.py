from functools import wraps

from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.request import Request


def role_required(*roles):
    if not roles:
        raise ValueError("role_required() needs at least one role.")

    def decorator(handler):
        @wraps(handler)
        def wrapper(*args, **kwargs):
            # Function views get (request, ...); class view methods (self, request, ...).
            request = args[0] if isinstance(args[0], Request) else args[1]
            if not request.user.is_authenticated:
                raise NotAuthenticated  # 401
            if request.user.role not in roles:
                raise PermissionDenied  # 403
            return handler(*args, **kwargs)
        return wrapper
    return decorator
