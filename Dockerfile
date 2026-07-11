FROM python:3.11-slim

WORKDIR /app

# Create a non-root user — the app has no reason to run as root
RUN useradd --system --no-create-home --shell /bin/false appuser

# Install dependencies as a separate cached layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY whatismyip/ whatismyip/
COPY config.py wsgi.py gunicorn.conf.py ./

# Include the example config so the app can self-bootstrap when no volume is mounted.
# In production the ./data volume mount overlays this with your real config.toml.
COPY data/config.toml.example data/

# Ensure the data directory (metrics DB, config) is writable by appuser
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["gunicorn", "--config", "gunicorn.conf.py", "--bind", "0.0.0.0:8000", "wsgi:application"]
