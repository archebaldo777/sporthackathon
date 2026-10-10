FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
# DejaVu — кириллический шрифт для генерации PDF-профилей
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
COPY validation_results ./validation_results
COPY start.sh ./start.sh
RUN useradd --create-home --uid 1000 draft && mkdir -p /app/var && chown -R draft:draft /app
USER draft
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=10 CMD curl -fs http://localhost:8000/api/health || exit 1
CMD ["./start.sh"]
