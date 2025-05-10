# Use an official Python image with pip pre‑installed
FROM python:3.11-slim

# Install ffmpeg (needed by yt-dlp/ffmpeg-python)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ffmpeg gcc libsndfile1 && \
    rm -rf /var/lib/apt/lists/*                                      # Clean up cache :contentReference[oaicite:0]{index=0}

WORKDIR /app

# Copy only requirements first to leverage cache
COPY requirements.txt .

# Install Python dependencies, including pip and gunicorn
RUN pip install --no-cache-dir -r requirements.txt                  # pip is present in python:3.11-slim :contentReference[oaicite:1]{index=1}

# Copy the rest of your app code
COPY . .

# Expose the Flask default port and start with Gunicorn
EXPOSE 8000
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000"]                  # Use one process per container :contentReference[oaicite:2]{index=2}

