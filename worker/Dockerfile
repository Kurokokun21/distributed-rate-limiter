FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY celery_app.py .

# Run one Celery worker process with an embedded Beat scheduler (--beat),
# so it both processes queued jobs and fires the periodic heartbeat.
CMD ["celery", "-A", "celery_app", "worker", "--beat", "--loglevel=info"]
