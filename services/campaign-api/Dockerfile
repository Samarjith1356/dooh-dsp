FROM python:3.12-slim
WORKDIR /app
COPY services/campaign-api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY services/campaign-api /app
COPY packages /packages
ENV PYTHONPATH=/app:/packages/ruleset/python:/packages/openrtb
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
