# core/log_filters.py
import logging, re
#add sensitive data redaction to log messages, so we don't accidentally log passwords or tokens.
_SENSITIVE = re.compile(
    r'(?i)("?(password|passwd|token|access|refresh|authorization|secret)"?\s*[:=]\s*"?)[^",\s}]+')

class RedactSensitiveFilter(logging.Filter):
    def filter(self, record):
        record.msg = _SENSITIVE.sub(r"\1[REDACTED]", record.getMessage())
        record.args = ()
        return True