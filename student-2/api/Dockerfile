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