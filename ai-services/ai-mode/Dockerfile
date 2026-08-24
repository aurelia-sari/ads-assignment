FROM python:3.11-slim

WORKDIR /app

COPY ai-mode/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ai-mode/app.py ./app.py
COPY prompts ./prompts

EXPOSE 5300

CMD ["python", "app.py"]
