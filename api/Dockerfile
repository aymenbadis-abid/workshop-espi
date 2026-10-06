FROM python:3.11-slim

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin app
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY ml_training ./ml_training
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
