FROM python:3.12-slim

# No .pyc files; logs appear immediately in `docker compose logs`
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /Server


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY . .


RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

#WebRTC/async work
CMD ["uvicorn", "pivot.asgi:application", "--host", "0.0.0.0", "--port", "8000"]