FROM python:3.13

# 1) Install Ruby, build-essential, cmake, libgit2-dev, and pkg-config
RUN apt-get update && apt-get install -y --no-install-recommends \
    ruby-full \
    build-essential \
    cmake \
    libgit2-dev \
    pkg-config \
 && gem install github-linguist \
 && rm -rf /var/lib/apt/lists/*

# The rest of your Docker steps
WORKDIR /app
COPY requirements.txt .
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements.txt

ARG ENV=production
RUN if [ "$ENV" = "development" ]; then pip install --no-cache-dir -r requirements-dev.txt; fi

COPY . .
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="${PYTHONPATH}:/app"
EXPOSE 8000
CMD ["python", "-m", "src.backend.api.main"]
