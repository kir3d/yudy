FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
COPY legal ./legal
COPY taxonomy ./taxonomy
COPY risk ./risk
COPY market ./market
COPY learn ./learn
COPY demo_provider ./demo_provider
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log --no-server-header --no-proxy-headers"]
