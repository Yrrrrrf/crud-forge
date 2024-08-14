# Set base image
FROM ubuntu:latest

# Metadata
LABEL maintainer="academic-hub"
LABEL version="0.1"

# Set the working directory in the container
WORKDIR /academic-hub

# Copy the requirements file
COPY requirements.txt .

# Install system dependencies and set up Python virtual environment
RUN \
    # Update package lists
    apt-get update && \
    # Install Python, pip, and venv
    apt-get install -y python3 python3-pip python3-venv && \
    # Create a virtual environment
    python3 -m venv /opt/venv && \
    # Make sure we use the virtualenv
    . /opt/venv/bin/activate && \
    # Upgrade pip in the virtual environment
    pip install --no-cache-dir --upgrade pip && \
    # Install Python packages from requirements.txt in the virtual environment
    pip install --no-cache-dir -r requirements.txt && \
    # Clean up apt cache to reduce image size
    apt-get clean && \
    # Remove unnecessary files to further reduce image size
    rm -rf /var/lib/apt/lists/*

# Set environment variable to use the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Copy the current directory contents into the container
COPY . .

# Expose ports
EXPOSE 8000 5173

# Default command
# CMD ["echo", "Academic Hub container is running..."]
# add another CMD to run the some.py file
CMD ["python", "some.py"]


