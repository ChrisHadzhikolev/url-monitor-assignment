# slim version for faster build
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

ENV HTTP_PORT=8080

EXPOSE $HTTP_PORT

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:${HTTP_PORT}/health', timeout=2)"

CMD ["python", "main.py"]