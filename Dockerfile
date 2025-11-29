FROM python:3.12-slim

# System deps (optional but helpful for common libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

WORKDIR /app

# Copy everything
COPY . .

# Install dependencies using uv
RUN uv sync --frozen --no-dev

EXPOSE 8000

# Run your app exactly like you do locally,
# but using $PORT for Railway compatibility.
CMD ["sh", "-c", "uv run main.py"]