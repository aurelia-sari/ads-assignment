FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY init_db.py .
COPY app.py .

EXPOSE 5204

# Seed at start, not build, so a seed change also reaches an existing volume.
CMD ["sh", "-c", "python init_db.py && exec python app.py"]
