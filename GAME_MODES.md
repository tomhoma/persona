# Game Modes Feature

## Overview

The game modes feature allows players to choose different categories of famous persons, making the game more focused and tailored to specific interests.

## Available Game Modes

### 🌟 All Persons
- **Description**: All famous Thai persons across all categories
- **Pool Size**: ~788 persons
- **Best For**: Players who want the full challenge with maximum variety

### 🎬 Entertainment
- **Description**: Actors, actresses, comedians, TV presenters
- **Occupations**: Film actors, TV actors, voice actors, stage actors, comedians, TV presenters, news presenters, models
- **Best For**: Fans of Thai cinema and television

### ⚽ Sports
- **Description**: Athletes, footballers, and sports personalities
- **Occupations**: Footballers, tennis players, badminton players, Muay Thai fighters, volleyball players, basketball players, esports players, athletes
- **Best For**: Sports enthusiasts

### 🎵 Music
- **Description**: Singers, musicians, composers, DJs
- **Occupations**: Singers, singer-songwriters, musicians, guitarists, composers, songwriters, rappers, dancers, choreographers, DJs
- **Best For**: Music lovers

### 👔 Important Persons
- **Description**: Politicians, leaders, and highly influential figures
- **Occupations**: Politicians, statesmen
- **Filter**: Minimum achievement score of 20 (only notable figures)
- **Best For**: Players interested in Thai politics and leadership

### 🎨 Arts & Culture
- **Description**: Directors, artists, writers, photographers
- **Occupations**: Film directors, producers, screenwriters, painters, photographers, illustrators, artists, graphic designers, writers, novelists, poets, playwrights, journalists
- **Best For**: Art and culture enthusiasts

### 📱 Social Media & Influencers
- **Description**: YouTubers, influencers, bloggers, content creators
- **Occupations**: YouTubers, influencers, bloggers
- **Filter**: Younger generation only (Millennials, Gen Z)
- **Best For**: Fans of modern digital content creators

## How It Works

### Backend Filtering

The backend filters persons based on:

1. **Occupation QIDs**: Checks if person has matching Wikidata occupation properties
2. **Career Domain**: Uses enriched narrative data to verify career category (if available)
3. **Achievement Score**: Some modes require minimum achievement level
4. **Era Category**: Some modes filter by generation (e.g., influencers are younger)

### Frontend Flow

1. **Mode Selection Screen**: Player sees all available modes with person counts
2. **Mode Selection**: Player clicks on desired mode card
3. **Start Game**: Player clicks "Start Game" button with selected mode
4. **Game Play**: Secret person is randomly selected from the filtered pool
5. **Game Info**: Mode and pool size displayed during gameplay
6. **New Game**: Player can change mode at any time

## API Endpoints

### GET /game_modes
Returns all available game modes with statistics.

**Response**:
```json
{
  "modes": [
    {
      "id": "all",
      "name": "All Persons",
      "name_th": "บุคคลทั้งหมด",
      "description": "All famous Thai persons across all categories",
      "description_th": "บุคคลชื่อดังทุกประเภท",
      "icon": "🌟",
      "count": 788
    },
    {
      "id": "entertainment",
      "name": "Entertainment",
      "name_th": "บันเทิง",
      "description": "Actors, actresses, comedians, TV presenters",
      "description_th": "นักแสดง ดารา นักแสดงตลก พิธีกร",
      "icon": "🎬",
      "count": 320
    }
    // ... more modes
  ]
}
```

### POST /start_game
Starts a new game with optional mode parameter.

**Request**:
```json
{
  "mode": "entertainment"  // optional, defaults to "all"
}
```

**Response**:
```json
{
  "sessionId": "uuid-here",
  "mode": "entertainment",
  "poolSize": 320
}
```

## Configuration

### Adding New Modes

Edit `backend/game_modes.py` and add to `GAME_MODES` dictionary:

```python
'your_mode_id': {
    'name': 'Mode Name',
    'name_th': 'ชื่อโหมด',
    'description': 'English description',
    'description_th': 'คำอธิบายภาษาไทย',
    'icon': '🎭',
    'occupation_filter': ['Q12345', 'Q67890'],  # Wikidata QIDs
    'career_domains': ['domain_name'],  # Optional
    'min_achievement_score': 10,  # Optional
    'era_categories': ['millennial', 'gen_z']  # Optional
}
```

### Filtering Logic

**occupation_filter**: List of Wikidata occupation QIDs. Person must have at least one matching occupation.

**career_domains**: List of career domains from enriched narrative data. Requires improved narrative embeddings.

**min_achievement_score**: Minimum achievement score (0-100). Higher score = more awards and recognition.

**era_categories**: List of allowed generation categories (pre_boomer, boomer, gen_x, millennial, millennial_late, gen_z).

## User Experience Benefits

1. **Focused Gameplay**: Players can focus on areas they know best
2. **Shorter Games**: Smaller pools = quicker rounds
3. **Thematic Learning**: Learn about specific domains (e.g., Thai sports history)
4. **Replayability**: Different modes offer fresh experiences
5. **Accessibility**: Newer players can start with smaller, familiar categories

## Technical Details

### Graceful Degradation

- If `game_modes.py` is missing, backend falls back to "all" mode only
- If improved embeddings unavailable, uses basic occupation filtering only
- Frontend shows person counts so players can see mode sizes

### Performance

- Mode statistics calculated on-demand (< 100ms for 788 persons)
- Person filtering happens once at game start
- No impact on guess/ranking performance

### Backward Compatibility

- Default mode is "all" (maintains original behavior)
- Existing API calls without mode parameter work unchanged
- Sessions store their mode for consistency

## Future Enhancements

Potential improvements:

1. **Custom Modes**: Let players create custom combinations
2. **Difficulty Levels**: Easy (well-known), Medium, Hard (obscure)
3. **Time Periods**: Filter by era (1950s-1970s, 1980s-2000s, 2000s-present)
4. **Region-Based**: Filter by birthplace or work location
5. **Collaborative Modes**: Teams or competitive modes
6. **Daily Challenges**: Pre-selected mode each day
7. **Achievement System**: Badges for winning in different modes

## Testing

To test game modes:

```bash
# 1. Ensure enriched narratives are generated (optional but recommended)
python scripts/enhanced_narrative_builder.py
python scripts/improved_narrative_embeddings.py

# 2. Start backend
cd backend
python -m uvicorn main:app --reload

# 3. Check available modes
curl http://localhost:8000/game_modes

# 4. Start game with specific mode
curl -X POST http://localhost:8000/start_game \
  -H "Content-Type: application/json" \
  -d '{"mode": "entertainment"}'

# 5. Start frontend
cd ../frontend
npm run dev
```

Navigate to the frontend and verify:
- Mode selection screen appears
- All modes show correct counts
- Selecting and starting game works
- Mode info displays during gameplay
- "Change Mode" button returns to selection

## Troubleshooting

### No persons found for mode

**Cause**: Mode filter too restrictive or data not populated

**Solution**: Check that persons have the required occupation QIDs in database

### Mode counts are 0

**Cause**: Occupation QIDs don't match any persons

**Solution**: Verify occupation QIDs exist in Wikidata and manifest

### Improved filtering not working

**Cause**: Enriched embeddings not generated

**Solution**: Run `enhanced_narrative_builder.py` and `improved_narrative_embeddings.py`

## Conclusion

The game modes feature significantly enhances PersonaGuess by:
- Providing tailored experiences for different interests
- Making the game more accessible to new players
- Increasing replayability with thematic variation
- Leveraging the rich occupation data from Wikidata
- Building on the improved narrative similarity system

Players can now enjoy PersonaGuess at their own level and focus on areas they're passionate about!
