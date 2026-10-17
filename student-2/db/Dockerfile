FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY init_db.py .
COPY app.py .

COPY entrypoint.sh .

EXPOSE 5202

CMD ["sh", "entrypoint.sh", "python", "app.py"]

HEALTHCHECK --interval=5s --timeout=3s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5202/health',timeout=2)"
