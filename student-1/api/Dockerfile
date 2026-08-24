FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY routes ./routes
COPY services ./services
COPY views ./views

EXPOSE 5101

CMD ["python", "app.py"]
