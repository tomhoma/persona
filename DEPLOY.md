# Production Deployment Guide
1. Copy all project files to your VPS.
2. **Build the database on the VPS:**
   - **Step 1: Create the Manifest:** `python3 scripts/create_manifest.py`
   - **Step 2: Fetch Raw Data:** `python3 scripts/fetch_data.py`
   - **Step 3: Populate Databases:** `python3 scripts/populate_databases.py`
3. **Build and run containers:** `sudo docker-compose up --build -d`
