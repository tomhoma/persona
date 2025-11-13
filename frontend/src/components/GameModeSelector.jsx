import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './GameModeSelector.css';

const API_URL = '';

function GameModeSelector({ onSelectMode, selectedMode }) {
  const [gameModes, setGameModes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchGameModes = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`${API_URL}/game_modes`);
        setGameModes(response.data.modes);
        setError(null);
      } catch (err) {
        setError("Could not load game modes");
        console.error('Error fetching game modes:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchGameModes();
  }, []);

  if (loading) {
    return <div className="game-mode-selector loading">Loading game modes...</div>;
  }

  if (error) {
    return <div className="game-mode-selector error">{error}</div>;
  }

  return (
    <div className="game-mode-selector">
      <h2>Choose Game Mode</h2>
      <div className="game-modes-grid">
        {gameModes.map((mode) => (
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
        ))}
      </div>
    </div>
  );
}

export default GameModeSelector;
