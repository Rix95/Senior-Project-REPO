FROM python:3.13

#Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY . /app

# Install the application dependencies
WORKDIR /app

RUN uv venv .venv
RUN uv pip install --no-cache -e .

# Add the current directory to Python path
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Run the application
CMD ["uvicorn", "main:app", "--port", "8000", "--host", "0.0.0.0"]

