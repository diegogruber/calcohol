FROM python:3.12-slim

RUN apt-get update && apt-get install -y build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv and dependencies
RUN pip install uv fasthtml pyyaml

WORKDIR /app
COPY . .

# Install dependencies using uv
RUN uv sync --frozen --no-dev

EXPOSE 8000

# Run the app (main.py already handles PORT and host)
CMD ["uv", "run", "main.py"]