FROM python:3.11-slim

WORKDIR /app

# Instalar dependências de sistema para o psycopg2
RUN apt-get update && apt-get install -y libpq-dev gcc

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

ENV FLASK_APP=run.py
ENV FLASK_ENV=development

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["flask", "run", "--host=0.0.0.0"]
