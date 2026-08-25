#!/bin/bash
# Stocker - Application Launch Script

# Allow custom ports via environment variables or default to 8088 / 5188
BACKEND_PORT=${BACKEND_PORT:-8088}
FRONTEND_PORT=${FRONTEND_PORT:-5188}

echo "========================================================="
echo "   Starting Stocker - Fundamental Stock Decision App   "
echo "========================================================="

# 1. Start Python FastAPI Backend
echo "Starting Backend API server on port $BACKEND_PORT..."
export PYTHONPATH="/home/dev/Projects/stocker/libs:/home/dev/Projects/stocker/backend:$PYTHONPATH"
export BACKEND_PORT=$BACKEND_PORT
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port $BACKEND_PORT &
BACKEND_PID=$!

# Wait a moment for backend to initialize
sleep 1

# 2. Start Vite Frontend
echo "Starting Frontend UI on port $FRONTEND_PORT..."
cd /home/dev/Projects/stocker/frontend
export FRONTEND_PORT=$FRONTEND_PORT
export BACKEND_PORT=$BACKEND_PORT
npx vite --host 0.0.0.0 --port $FRONTEND_PORT &
FRONTEND_PID=$!

echo "---------------------------------------------------------"
echo " Backend running at:  http://localhost:$BACKEND_PORT"
echo " API Docs at:         http://localhost:$BACKEND_PORT/docs"
echo " Frontend running at: http://localhost:$FRONTEND_PORT"
echo "---------------------------------------------------------"
echo "Tip: You can customize ports anytime, e.g.:"
echo "     BACKEND_PORT=9000 FRONTEND_PORT=3000 ./start.sh"
echo "---------------------------------------------------------"
echo "Press Ctrl+C to terminate all services."

# Trap SIGINT / SIGTERM to clean up background processes
trap "echo 'Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
