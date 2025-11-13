# Deploying New Features to Docker

This guide shows how to update your running Docker deployment with the improved narrative similarity system and game mode selection feature.

## Quick Update (Code Only)

If you just want to deploy the new code without improved embeddings:

```bash
# 1. Pull latest code
git pull origin main

# 2. Rebuild and restart containers
sudo docker-compose down
sudo docker-compose up --build -d

# 3. Check logs
sudo docker-compose logs -f backend
```

The game modes will work with basic occupation filtering, and narrative similarity will use the simple method.

## Full Update (With Improved Embeddings)

To get the full benefits of improved narrative similarity and advanced game mode filtering:

### Step 1: Generate Improved Embeddings (On VPS)

```bash
# Navigate to project directory
cd /path/to/persona

# Activate Python environment if needed
# source venv/bin/activate

# Generate enriched narratives (~6 minutes for 788 persons)
python3 scripts/enhanced_narrative_builder.py

# Generate improved embeddings (~13 minutes)
python3 scripts/improved_narrative_embeddings.py
```

**Expected output**:
```
✅ Enriched narratives created!
   Total processed: 788
   Average achievement score: 28.4
   Domain distribution:
     entertainment: 320
     sports: 215
     music: 85
     ...

✅ Improved embeddings created!
   Total persons: 788
   Model: paraphrase-multilingual-MiniLM-L12-v2
   Embedding dimensions: 384
```

### Step 2: Verify Data Files

```bash
# Check that new directories exist
ls -lh data/enriched/
ls -lh data/narrative_embeddings/

# Should see JSON files for each person
ls data/enriched/*.json | wc -l
# Should output: 788 (or your total person count)
```

### Step 3: Rebuild Docker Containers

```bash
# Stop existing containers
sudo docker-compose down

# Rebuild with new code
sudo docker-compose up --build -d
```

### Step 4: Verify Everything Works

```bash
# Check backend logs for confirmation
sudo docker-compose logs backend | grep "INFO"
```

**Look for these lines**:
```
INFO: Using improved multi-aspect narrative similarity for 788 persons.
INFO: Game modes available
```

**If you see this instead**:
```
INFO: Using simple cosine similarity for narrative comparison.
```
Then improved embeddings weren't found. Check Step 1.

### Step 5: Test in Browser

1. Open your site: `http://your-vps-ip`
2. You should see the game mode selection screen
3. Try different modes (Entertainment, Sports, etc.)
4. Verify person counts show for each mode
5. Start a game and check rankings are accurate

## Directory Structure After Update

```
persona/
├── data/
│   ├── raw/                    # Existing
│   ├── enriched/               # NEW - ~12MB
│   │   ├── Q*.json
│   │   └── _enrichment_summary.json
│   ├── narrative_embeddings/   # NEW - ~18MB
│   │   ├── Q*.json
│   │   └── _all_embeddings.json
│   ├── persona.db              # Existing
│   └── chroma/                 # Existing
├── backend/
│   ├── main.py                 # Updated
│   ├── game_modes.py           # NEW
│   └── improved_similarity.py  # NEW
└── frontend/                   # Updated
```

## Docker Volume Persistence

The `data/` directory is mounted as a volume in docker-compose.yml:

```yaml
backend:
  volumes: ['./data:/app/data']
```

This means:
- ✅ Data persists between container restarts
- ✅ New data files (enriched/, narrative_embeddings/) are automatically available
- ✅ No need to copy files into container

## Troubleshooting

### Issue: "Improved embeddings directory not found"

**Cause**: Step 1 wasn't completed or files in wrong location

**Solution**:
```bash
# Ensure you're in project root
pwd
# Should show: /path/to/persona

# Run scripts again
python3 scripts/enhanced_narrative_builder.py
python3 scripts/improved_narrative_embeddings.py

# Verify output directories exist
ls data/enriched/
ls data/narrative_embeddings/
```

### Issue: "Module game_modes not found"

**Cause**: New code not built into container

**Solution**:
```bash
# Force rebuild (no cache)
sudo docker-compose build --no-cache backend
sudo docker-compose up -d
```

### Issue: Import error for sentence-transformers

**Cause**: Missing Python dependency

**Solution**: Add to `requirements.txt` (should already be there):
```
sentence-transformers
```

Then rebuild:
```bash
sudo docker-compose build backend
sudo docker-compose up -d
```

### Issue: Out of memory during embedding generation

**Cause**: VPS has limited RAM

**Solution 1 - Use lighter model**:
Edit `scripts/improved_narrative_embeddings.py` line 22:
```python
MODEL_NAME = 'all-MiniLM-L6-v2'  # Lighter model
```

**Solution 2 - Process in batches**:
Generate embeddings on local machine, then upload:
```bash
# On local machine
python3 scripts/enhanced_narrative_builder.py
python3 scripts/improved_narrative_embeddings.py

# Upload to VPS
rsync -avz data/enriched/ user@vps:/path/to/persona/data/enriched/
rsync -avz data/narrative_embeddings/ user@vps:/path/to/persona/data/narrative_embeddings/
```

### Issue: Game modes showing 0 persons

**Cause**: Occupation QIDs don't match database

**Solution**: Check mode definitions in `backend/game_modes.py` match your data

## Performance Considerations

### Initial Generation (One-time)
- Enriched narratives: ~6 minutes
- Improved embeddings: ~13 minutes
- Total: ~19 minutes

### Docker Container Startup
- Without improved embeddings: ~2-3 seconds
- With improved embeddings: ~5-6 seconds (+3 seconds to load files)

### Runtime Performance
- Similarity calculations: Same speed (pre-computed)
- Mode filtering: < 100ms
- No impact on gameplay

### Storage
- Enriched narratives: ~12 MB
- Improved embeddings: ~18 MB
- Total new data: ~30 MB (minimal)

## Production Deployment Checklist

- [ ] Pull latest code from repository
- [ ] Generate enriched narratives
- [ ] Generate improved embeddings
- [ ] Verify data files created
- [ ] Stop Docker containers
- [ ] Rebuild containers with new code
- [ ] Start containers
- [ ] Check backend logs for confirmation
- [ ] Test game mode selection in browser
- [ ] Verify improved similarity is active
- [ ] Test gameplay with different modes
- [ ] Monitor performance and logs

## Rollback Plan

If something goes wrong:

```bash
# 1. Stop new containers
sudo docker-compose down

# 2. Checkout previous version
git checkout <previous-commit-hash>

# 3. Rebuild and start
sudo docker-compose up --build -d
```

The old code will still work with the new data files (it just won't use them).

## Maintenance

### Regenerating Embeddings

If you update the person database:

```bash
# 1. Run data pipeline
python3 scripts/fetch_data.py
python3 scripts/populate_databases.py

# 2. Regenerate enriched data
rm -rf data/enriched data/narrative_embeddings
python3 scripts/enhanced_narrative_builder.py
python3 scripts/improved_narrative_embeddings.py

# 3. Restart backend
sudo docker-compose restart backend
```

### Monitoring

Check backend logs regularly:
```bash
# View real-time logs
sudo docker-compose logs -f backend

# Check for errors
sudo docker-compose logs backend | grep ERROR

# Check which system is active
sudo docker-compose logs backend | grep "Using improved"
```

## Summary

**Quick update (5 minutes)**:
```bash
git pull
sudo docker-compose down
sudo docker-compose up --build -d
```

**Full update with improved embeddings (30 minutes)**:
```bash
git pull
python3 scripts/enhanced_narrative_builder.py
python3 scripts/improved_narrative_embeddings.py
sudo docker-compose down
sudo docker-compose up --build -d
```

Both work! The full update gives you the best accuracy and advanced filtering, but the quick update still adds game modes with basic filtering.
