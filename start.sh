#!/bin/bash

# Start the FastAPI backend
echo "🚀 Starting EcoRoute Optimizer Backend..."
python main.py &
BACKEND_PID=$!

# Wait for backend to start
sleep 2

# Check if backend is running
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Backend running on http://localhost:8000"
    echo "📱 Open frontend.html in your browser to use the app"
    echo ""
    echo "Press Ctrl+C to stop the backend"
    
    # Wait for Ctrl+C
    trap "echo '🛑 Stopping backend...'; kill $BACKEND_PID; exit" INT
    wait $BACKEND_PID
else
    echo "❌ Backend failed to start"
    exit 1
fi
