FROM python:3.13

# Set the working directory in the container
WORKDIR /app

# Copy the requirements files into the container
COPY requirements.txt .
COPY requirements-dev.txt .

# Install production dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Optionally install development dependencies (for development only)
ARG ENV=production
RUN if [ "$ENV" = "development" ]; then pip install --no-cache-dir -r requirements-dev.txt; fi

# Copy the rest of the application code
COPY . .

# Add the virtual environment to the PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Expose the port the app runs on
EXPOSE 8000

# Run the FastAPI app directly using Python
CMD ["python", "-m", "src.backend.api.main"]