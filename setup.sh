#!/bin/bash

# setup.sh
# Comprehensive environment setup for backend and frontend

# 1. Backend Setup
if [ ! -d ".venv" ]; then
    echo "Creating backend virtual environment..."
    python3 -m venv .venv
fi

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Installing backend dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 2. Frontend Setup
echo "Installing frontend dependencies..."
if [ -d "frontend" ]; then
    cd frontend
    npm install
    cd ..
else
    echo "Error: frontend directory not found."
    exit 1
fi

echo "Setup complete."
