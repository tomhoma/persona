import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './GameModeSelector.css';

const API_URL = '';

// Fallback mode if backend doesn't support game modes yet
const FALLBACK_MODE = {
  id: 'all',
  name: 'All Persons',
  name_th: 'บุคคลทั้งหมด',
  description: 'All famous Thai persons',
  description_th: 'บุคคลชื่อดังทั้งหมด',
  icon: '🌟',
  count: '...'
};

function GameModeSelector({ onSelectMode, selectedMode }) {
  const [gameModes, setGameModes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchGameModes = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`${API_URL}/game_modes`);

        // Check if response is valid JSON and has modes
        if (response.data && response.data.modes && Array.isArray(response.data.modes)) {
          setGameModes(response.data.modes);
          setError(null);
        } else {
          // Backend doesn't support game modes, use fallback
          console.warn('Backend does not support game modes, using fallback');
          setGameModes([FALLBACK_MODE]);
          setError(null);
        }
      } catch (err) {
        // Backend error or old version - use fallback
        console.warn('Could not load game modes, using fallback:', err.message);
        setGameModes([FALLBACK_MODE]);
        setError(null);
      } finally {
        setLoading(false);
      }
    };

    fetchGameModes();
  }, []);

  if (loading) {
    return <div className="game-mode-selector loading">Loading game modes...</div>;
  }

  return (
    <div className="game-mode-selector">
      <h2>Choose Game Mode</h2>
      {error && (
        <div className="mode-warning">
          Using default mode - update backend for more options
        </div>
      )}
      <div className="game-modes-grid">
        {gameModes && gameModes.length > 0 ? (
          gameModes.map((mode) => (
            <button
              key={mode.id}
              className={`game-mode-card ${selectedMode === mode.id ? 'selected' : ''}`}
              onClick={() => onSelectMode(mode.id)}
            >
              <div className="mode-icon">{mode.icon}</div>
              <div className="mode-name">{mode.name}</div>
              <div className="mode-description">{mode.description}</div>
              <div className="mode-count">{mode.count} persons</div>
            </button>
          ))
        ) : (
          <div className="no-modes">
            <p>Loading modes...</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default GameModeSelector;
