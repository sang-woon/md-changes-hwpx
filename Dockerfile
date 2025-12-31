FROM python:3.11-slim

# Install Pandoc and other dependencies
RUN apt-get update && apt-get install -y \
    pandoc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY src/ src/
COPY data/ data/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Expose port
EXPOSE 8000

# Run the server
CMD ["uvicorn", "hwpx_converter.api:app", "--host", "0.0.0.0", "--port", "8000"]
