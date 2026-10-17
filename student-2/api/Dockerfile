FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY routes ./routes
COPY services ./services
COPY views ./views
COPY prompts ./prompts
COPY agentic_loop ./agentic_loop

EXPOSE 5102

CMD ["python", "app.py"]
HEALTHCHECK --interval=5s --timeout=3s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5102/health',timeout=2)"
