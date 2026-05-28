#!/bin/bash
# AI Judge Prediction Pool - Deployment Script
# Usage: bash deploy.sh [local|vercel|github]

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

case "${1:-local}" in
  local)
    echo "🚀 Starting local server..."
    cd "$DIR"
    pip install -r requirements.txt -q 2>/dev/null
    python app.py
    ;;
  vercel)
    echo "🚀 Deploying to Vercel..."
    cd "$DIR"
    pip install -r requirements.txt -q 2>/dev/null
    vercel --prod
    echo "✅ Deployed! Check the URL above."
    ;;
  github)
    echo "🚀 Pushing to GitHub..."
    cd "$DIR"
    git init 2>/dev/null || true
    git add .
    git commit -m "AI Judge Prediction Pool" 2>/dev/null || git commit -m "Update"
    echo "📝 Now run: git remote add origin https://github.com/YOUR_USERNAME/ai-judge-pool.git"
    echo "📝 Then run: git push -u origin main"
    ;;
  *)
    echo "Usage: bash deploy.sh [local|vercel|github]"
    ;;
esac
