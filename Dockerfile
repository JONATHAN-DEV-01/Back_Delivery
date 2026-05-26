FROM python:3.11-slim

WORKDIR /app

# Dependências de sistema para psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

ENV FLASK_APP=run.py
# Produção: não usar modo debug
ENV FLASK_ENV=production

COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
# Gunicorn: servidor WSGI de produção
# WEB_CONCURRENCY pode ser sobrescrito via env var no Render (default 2)
CMD ["sh", "-c", "gunicorn run:app --bind 0.0.0.0:5000 --workers ${WEB_CONCURRENCY:-2} --timeout 120"]
