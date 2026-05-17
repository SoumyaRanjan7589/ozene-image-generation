cat > deploy.sh << 'EOF'
#!/bin/bash
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Deploying Image Generation API"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ">>> [1/3] Pulling latest code..."
git pull origin main

echo ">>> [2/3] Building and restarting container..."
docker compose up -d --build

echo ">>> [3/3] Cleaning up old images..."
docker image prune -f

echo ""
echo "Deployed! Checking health..."
sleep 3
curl -sf http://localhost:8001/api/v1/health | python3 -m json.tool \
  || echo "Health check failed — run: docker logs myapp"
EOF

chmod +x deploy.sh