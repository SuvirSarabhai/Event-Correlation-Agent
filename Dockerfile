FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer — only rebuilds if requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# Ensure Python output is not buffered (so logs appear immediately in ECS)
ENV PYTHONUNBUFFERED=1

# Run the correlation agent polling loop
CMD ["python", "run.py"]
