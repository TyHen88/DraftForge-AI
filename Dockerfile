FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml README.md /app/
COPY writer_ai_assistant /app/writer_ai_assistant

RUN pip install -U pip && pip install .

CMD ["python", "-m", "writer_ai_assistant"]

