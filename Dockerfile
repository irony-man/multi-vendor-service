FROM python:3.9-slim-buster


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies. `build-essential` is needed for some Python packages
# that compile from source.
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first to leverage Docker's layer caching.
# This step will only be re-run if requirements.txt changes.
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project directory into the container's working directory
COPY . .

# Copy the new scripts into their respective locations in the container
COPY entrypoint.sh /usr/local/bin/
COPY healthcheck.py /app/

# Make the entrypoint script executable so the system can run it
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint script to be executed when the container starts.
# This script will run before the CMD.
ENTRYPOINT ["entrypoint.sh"]

# The command that the entrypoint script will execute *after* the health check passes.
CMD ["gunicorn", "multi_vendor_project.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
