#!/bin/bash
source .venv/bin/activate
uvicorn app.api:app --host 127.0.0.1 --port 8000 > uvicorn.log 2>&1 &
PID=$!
sleep 3
echo "Running curl..."
curl -s -X POST http://127.0.0.1:8000/api/chat -H "Content-Type: application/json" -d '{"message": "Which product sold the most yesterday?"}' > test_output.json
echo "Kill server..."
kill $PID
cat test_output.json
