FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY services/ ./services/
COPY views/ ./views/
COPY route/ ./route/

EXPOSE 5105

CMD ["python", "app.py"]
