# Production Deployment Guide
1. Copy all project files to your VPS.
2. **Build the database on the VPS:** \`for i in {0..9}; do python3 scripts/process_data.py \$i; done\`
3. **Build and run containers:** \`sudo docker-compose up --build -d\`
