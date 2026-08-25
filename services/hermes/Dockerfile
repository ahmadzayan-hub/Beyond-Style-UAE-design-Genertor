FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Never bakes ANTHROPIC_API_KEY into the image — it's injected at
# deploy time as a secret env var (see backend/.env.example / README
# in this directory). The service is fully honest with no key set: it
# reports SKIPPED_EXTERNAL_MODEL rather than failing to boot.
ENV PYTHONUNBUFFERED=1
EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import httpx; httpx.get('http://localhost:8100/health', timeout=3).raise_for_status()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
