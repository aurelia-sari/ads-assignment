FROM python:3.11-slim

WORKDIR /app

COPY agentic-loop/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY agentic-loop/*.py ./
COPY prompts ./prompts

# ENTRYPOINT rather than CMD so `docker compose run --rm agentic-loop all 2`
# appends its arguments instead of replacing the command.
ENTRYPOINT ["python", "main.py"]
