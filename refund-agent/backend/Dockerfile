FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend files
COPY . .

# Seed databases inside the container so they are ready on startup
RUN python data/seed_db.py

EXPOSE 8080

ENV PORT=8080

CMD ["python", "main.py"]
