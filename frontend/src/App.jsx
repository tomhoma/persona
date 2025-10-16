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
        
        // First get all persons and a random secret person
        const [personsRes, secretRes] = await Promise.all([
          axios.get(`${API_URL}/persons`),
          axios.get(`${API_URL}/random_secret`)
        ]);
        
        setAllPersons(personsRes.data);
        setSecretPerson(secretRes.data);
        
        // Then get the daily ranking based on the random secret person
        const rankingRes = await axios.get(`${API_URL}/daily_ranking?secret_qid=${secretRes.data.qid}`);
        setDailyRanking(new Map(rankingRes.data.map(p => [p.qid, p])));
        
      } catch (err) {
        setError("Could not connect to server.");
        console.error('Error fetching game data:', err);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchGameData();
  }, []);

  const handleGuess = (person) => {
    if (isGameWon || isResigned || !dailyRanking || !person || !secretPerson) return;
    
    const result = dailyRanking.get(person.qid);
    if (!result) return;
    
    const newGuesses = [...guesses, result];
    setGuesses(newGuesses.sort((a, b) => a.rank - b.rank));
    
    if (result.qid === secretPerson.qid) {
      setIsGameWon(true);
    }
  };

  const handleResign = () => {
    if (isGameWon || isResigned || !secretPerson || !dailyRanking) return;
    
    setIsResigned(true);
    
    // Add the secret person to guesses if not already guessed
    const secretResult = dailyRanking.get(secretPerson.qid);
    if (secretResult && !guesses.find(g => g.qid === secretPerson.qid)) {
      const newGuesses = [...guesses, secretResult];
      setGuesses(newGuesses.sort((a, b) => a.rank - b.rank));
    }
  };

  const startNewGame = () => {
    setGuesses([]);
    setIsGameWon(false);
    setIsResigned(false);
    setSecretPerson(null);
    setDailyRanking(null);
    
    // Fetch new random secret person and ranking
    const fetchNewGame = async () => {
      try {
        setIsLoading(true);
        
        // First get the random secret person
        const secretRes = await axios.get(`${API_URL}/random_secret`);
        setSecretPerson(secretRes.data);
        
        // Then get the ranking based on the secret person
        const rankingRes = await axios.get(`${API_URL}/daily_ranking?secret_qid=${secretRes.data.qid}`);
        setDailyRanking(new Map(rankingRes.data.map(p => [p.qid, p])));
        
      } catch (err) {
        setError("Could not start new game.");
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchNewGame();
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
            {isGameWon && (
              <div className="win-message">
                <h2>🎉 Congratulations!</h2>
                <p>You found: {secretPerson?.label}</p>
              </div>
            )}
            {isResigned && !isGameWon && (
              <div className="resign-message">
                <h2>Game Over</h2>
                <p>The answer was: <strong>{secretPerson?.label}</strong></p>
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
            {(isGameWon || isResigned) && secretPerson && (
              <TopRelations 
                dailyRanking={dailyRanking} 
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
