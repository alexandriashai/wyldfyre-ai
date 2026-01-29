FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install Python dependencies
COPY services/browser/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium only for smaller image)
RUN playwright install chromium

# Copy service code
COPY services/browser/src /app/src

# Create directories for screenshots and sessions
RUN mkdir -p /tmp/browser_screenshots /tmp/browser_sessions

# Expose health check port
EXPOSE 8002

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Run the service
CMD ["python", "-m", "src.main"]
