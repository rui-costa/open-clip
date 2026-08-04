# Kill existing processes
pkill -f "python -m backend.api"
pkill -f "vite"

cd frontend
npm run dev &
cd ..
.venv/bin/python -m backend.api