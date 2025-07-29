#!/bin/bash
# DigitalOcean startup script

# Set the port from environment variable or default to 8080
export PORT=${PORT:-8080}
export API_PORT=$PORT

# Start the application
exec python -m uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1