import React, { useState, useEffect } from 'react';
import axios from 'axios';
import GuessInput from './components/GuessInput';
import GuessList from './components/GuessList';
import TopRelations from './components/TopRelations';
import GameModeSelector from './components/GameModeSelector';
import './App.css';

const API_URL = '';

function App() {
  const [allPersons, setAllPersons] = useState([]);
  const [dailyRanking, setDailyRanking] = useState(null);
  const [secretPerson, setSecretPerson] = useState(null);
  const [guesses, setGuesses] = useState([]);
  const [isGameWon, setIsGameWon] = useState(false);
  const [isResigned, setIsResigned] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Game mode state
  const [gameStarted, setGameStarted] = useState(false);
  const [selectedMode, setSelectedMode] = useState('all');
  const [currentMode, setCurrentMode] = useState('all');
  const [poolSize, setPoolSize] = useState(0);

  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // Get all persons (this is safe to expose)
        const personsRes = await axios.get(`${API_URL}/persons`);
        setAllPersons(personsRes.data);

      } catch (err) {
        setError("Could not connect to server.");
        console.error('Error fetching initial data:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchInitialData();
  }, []);

  const startGame = async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Start a new game session with selected mode
      const gameRes = await axios.post(`${API_URL}/start_game`, {
        mode: selectedMode
      });
      const { sessionId, mode, poolSize } = gameRes.data;

      // Store session ID and game info
      localStorage.setItem('gameSessionId', sessionId);
      setCurrentMode(mode);
      setPoolSize(poolSize);

      // Reset game state
      setGuesses([]);
      setIsGameWon(false);
      setIsResigned(false);
      setDailyRanking(null);
      setSecretPerson({ qid: 'hidden', label: 'Unknown' });
      setGameStarted(true);

    } catch (err) {
      setError("Could not start game.");
      console.error('Error starting game:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGuess = async (person) => {
    if (isGameWon || isResigned || !person) return;

    try {
      const sessionId = localStorage.getItem('gameSessionId');
      if (!sessionId) {
        setError("Game session expired. Please refresh.");
        return;
      }

      // Send guess to server for validation
      const guessRes = await axios.post(`${API_URL}/make_guess`, {
        sessionId,
        qid: person.qid
      });

      const { isCorrect, result, gameWon } = guessRes.data;

      const newGuesses = [...guesses, result];
      setGuesses(newGuesses.sort((a, b) => a.rank - b.rank));

      // Build dailyRanking map from guesses (only show guessed persons)
      const newDailyRanking = new Map();
      newGuesses.forEach(guess => {
        newDailyRanking.set(guess.qid, guess);
      });
      setDailyRanking(newDailyRanking);

      if (gameWon) {
        setIsGameWon(true);
      }

    } catch (err) {
      setError("Could not process guess.");
      console.error('Error making guess:', err);
    }
  };

  const handleResign = async () => {
    if (isGameWon || isResigned) return;

    try {
      const sessionId = localStorage.getItem('gameSessionId');
      if (!sessionId) {
        setError("Game session expired. Please refresh.");
        return;
      }

      // Send resign request to server
      const resignRes = await axios.post(`${API_URL}/resign_game`, {
        sessionId
      });

      const { secretPerson: revealedSecret, result } = resignRes.data;

      setIsResigned(true);
      setSecretPerson(revealedSecret);

      // Add the secret person to guesses
      const newGuesses = [...guesses];
      if (!guesses.find(g => g.qid === revealedSecret.qid)) {
        newGuesses.push(result);
        setGuesses(newGuesses.sort((a, b) => a.rank - b.rank));
      }

      // Build dailyRanking map from all guesses including the secret
      const newDailyRanking = new Map();
      newGuesses.forEach(guess => {
        newDailyRanking.set(guess.qid, guess);
      });
      setDailyRanking(newDailyRanking);

    } catch (err) {
      setError("Could not resign game.");
      console.error('Error resigning game:', err);
    }
  };

  const handleBackToModeSelection = () => {
    setGameStarted(false);
    setGuesses([]);
    setIsGameWon(false);
    setIsResigned(false);
    setSecretPerson(null);
    setDailyRanking(null);
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>PersonaGuess</h1>
        {gameStarted && !isLoading && !error && (
          <button onClick={handleBackToModeSelection} className="new-game-btn">
            Change Mode / New Game
          </button>
        )}
      </header>
      <main>
        {isLoading ? (
          <p>Loading...</p>
        ) : error ? (
          <p className="error-message">{error}</p>
        ) : !gameStarted ? (
          // Show game mode selector before game starts
          <div className="mode-selection-screen">
            <GameModeSelector
              onSelectMode={setSelectedMode}
              selectedMode={selectedMode}
            />
            <div className="start-game-container">
              <button
                onClick={startGame}
                className="start-game-btn"
                disabled={!selectedMode}
              >
                Start Game {selectedMode && `(${selectedMode === 'all' ? 'All Persons' : selectedMode})`}
              </button>
            </div>
          </div>
        ) : (
          // Show game interface
          <>
            <div className="game-info">
              <span className="mode-badge">
                Mode: {currentMode === 'all' ? 'All Persons' : currentMode}
              </span>
              <span className="pool-size-badge">
                Pool: {poolSize} persons
              </span>
            </div>

            {isGameWon && secretPerson && secretPerson.qid !== 'hidden' && (
              <div className="win-message">
                <h2>🎉 Congratulations!</h2>
                <p>You found: {secretPerson.label}</p>
              </div>
            )}
            {isResigned && !isGameWon && secretPerson && secretPerson.qid !== 'hidden' && (
              <div className="resign-message">
                <h2>Game Over</h2>
                <p>The answer was: <strong>{secretPerson.label}</strong></p>
                <p>Better luck next time!</p>
              </div>
            )}
            <div className="game-controls">
              <GuessInput
                allPersons={allPersons}
                onGuess={handleGuess}
                disabled={isGameWon || isResigned}
              />
              {!isGameWon && !isResigned && guesses.length > 0 && (
                <button onClick={handleResign} className="resign-btn">
                  Resign & Reveal Answer
                </button>
              )}
            </div>
            <GuessList guesses={guesses} />
            {(isGameWon || isResigned) && secretPerson && secretPerson.qid !== 'hidden' && (
              <TopRelations
                sessionId={localStorage.getItem('gameSessionId')}
                secretQid={secretPerson.qid}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default App;
