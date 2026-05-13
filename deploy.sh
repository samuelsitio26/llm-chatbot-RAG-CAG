#!/bin/bash
# ============================================================
# deploy.sh - Quick deploy script for toba-backend VPS
# Usage: bash deploy.sh
# ============================================================

set -e

PROJECT_DIR=~/llm-chatbot-RAG-CAG
PORT=8000

echo "============================================================"
echo "🚀 Deploying latest changes from GitHub..."
echo "============================================================"

cd $PROJECT_DIR

# 1. Pull latest code
echo ""
echo "📥 Pulling latest code..."
git pull origin main

# 2. Kill stray process on port if any
echo ""
echo "🔍 Checking port $PORT..."
if lsof -i :$PORT > /dev/null 2>&1; then
    echo "⚠️  Port $PORT in use, freeing it..."
    fuser -k ${PORT}/tcp 2>/dev/null || true
    sleep 3
    echo "✅ Port $PORT freed"
else
    echo "✅ Port $PORT is free"
fi

# 3. Restart backend
echo ""
echo "🔄 Restarting toba-backend..."
pm2 restart toba-backend

# 4. Show status
echo ""
echo "============================================================"
echo "✅ Deploy complete!"
echo "============================================================"
sleep 3
pm2 status
