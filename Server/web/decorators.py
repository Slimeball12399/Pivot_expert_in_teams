from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def role_required(role):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                # Not logged in: send to the login page, then back here afterwards.
                return redirect_to_login(request.get_full_path())
            if request.user.role != role:
                # Logged in but wrong role: 403.
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
