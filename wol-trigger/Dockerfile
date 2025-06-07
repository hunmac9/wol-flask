FROM python:3.9-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends wakeonlan && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
# Default ENV variables (will be overridden by docker-compose)
ENV FLASK_APP=app.py
ENV NAS_SCHEME=http
ENV WOL_PORT=9
# No default for mandatory NAS_MAC_ADDRESS, NAS_IP, NAS_PORT - must be set in compose
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]