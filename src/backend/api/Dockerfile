FROM python:3.13

#Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY . /app

# Install the application dependencies
WORKDIR /app
RUN uv sync --frozen --no-cache

# Run the application
CMD ["/app/.venv/bin/uvicorn", "main:app", "--port", "8000", "--host", "0.0.0.0"] 

