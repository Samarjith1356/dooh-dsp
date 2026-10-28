FROM python:3.12-slim
WORKDIR /app
COPY agents/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY agents /app/agents
COPY infra /app/infra
COPY apps/web /app/apps/web
COPY services /app/services
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
EXPOSE 8091
CMD ["python", "-m", "agents.orchestrator"]
