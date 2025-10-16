import React, { useState, useEffect } from 'react';
import axios from 'axios';
import GuessInput from './components/GuessInput';
import GuessList from './components/GuessList';
import TopRelations from './components/TopRelations';
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

  useEffect(() => {
    const fetchGameData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        
        // Get all persons (this is safe to expose)
        const personsRes = await axios.get(`${API_URL}/persons`);
        setAllPersons(personsRes.data);
        
        // Start a new game session (server will generate secret and return session ID)
        const gameRes = await axios.post(`${API_URL}/start_game`);
        const { sessionId } = gameRes.data;
        
        // Store session ID for future requests
        localStorage.setItem('gameSessionId', sessionId);
        
        // Don't store any ranking data initially to prevent secret exposure
        setDailyRanking(null);
        
        // Don't store secret person data on client side
        setSecretPerson({ qid: 'hidden', label: 'Unknown' });
        
      } catch (err) {
        setError("Could not connect to server.");
        console.error('Error fetching game data:', err);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchGameData();
  }, []);

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

  const startNewGame = async () => {
    setGuesses([]);
    setIsGameWon(false);
    setIsResigned(false);
    setSecretPerson({ qid: 'hidden', label: 'Unknown' });
    setDailyRanking(null);
    
    try {
      setIsLoading(true);
      setError(null);
      
      // Start a new game session (server will generate new secret)
      const gameRes = await axios.post(`${API_URL}/start_game`);
      const { sessionId } = gameRes.data;
      
      // Store new session ID
      localStorage.setItem('gameSessionId', sessionId);
      
      // Don't store any ranking data initially to prevent secret exposure
      setDailyRanking(null);
      
    } catch (err) {
      setError("Could not start new game.");
      console.error('Error starting new game:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>PersonaGuess</h1>
        {!isLoading && !error && (
          <button onClick={startNewGame} className="new-game-btn">
            New Game
          </button>
        )}
      </header>
      <main>
        {isLoading ? (
          <p>Loading...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <>
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
