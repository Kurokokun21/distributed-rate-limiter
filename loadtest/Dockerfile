FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY locustfile.py .

# Start Locust pointed at the api service. Its web dashboard serves on 8089.
# --class-picker shows checkboxes to choose which user class to run.
CMD ["locust", "-f", "locustfile.py", "--host", "http://api:8000", "--class-picker"]
