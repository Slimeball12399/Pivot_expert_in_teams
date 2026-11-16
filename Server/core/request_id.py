# core/request_id.py
import contextvars, logging, re, uuid

request_id_var = contextvars.ContextVar("request_id", default="-")
_VALID = re.compile(r"^[A-Za-z0-9-]{8,64}$")

class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-ID", "")
        rid = incoming if _VALID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(rid)
        request.request_id = rid
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response["X-Request-ID"] = rid
        return response

class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True