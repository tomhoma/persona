import React, { useState, useEffect } from 'react';
import axios from 'axios';
import GuessInput from './components/GuessInput';
import GuessList from './components/GuessList';
import './App.css';

// For production, the frontend will be served by Nginx and will proxy API requests.
// For local development, it connects to localhost.
const API_URL = import.meta.env.PROD ? '' : 'http://localhost:8000';
const SECRET_PERSON_QID = 'Q307'; // Galileo Galilei - for development

function App() {
  const [allPersons, setAllPersons] = useState([]);
  const [dailyRanking, setDailyRanking] = useState(null);
  const [guesses, setGuesses] = useState([]);
  const [isGameWon, setIsGameWon] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchGameData = async () => {
      try {
        const personsPromise = axios.get(`${API_URL}/persons`);
        const rankingPromise = axios.get(`${API_URL}/daily_ranking?secret_qid=${SECRET_PERSON_QID}`);

        const [personsResponse, rankingResponse] = await Promise.all([personsPromise, rankingPromise]);

        setAllPersons(personsResponse.data);
        // Create a map for quick lookups
        const rankingMap = new Map(rankingResponse.data.map(p => [p.qid, p]));
        setDailyRanking(rankingMap);

      } catch (err) {
        console.error("Error fetching game data:", err);
        setError("Could not connect to the game server. Please try again later.");
      } finally {
        setIsLoading(false);
      }
    };

    // The server needs a moment to load its own cache
    setTimeout(() => {
        fetchGameData();
    }, 1000);

  }, []);

  const handleGuess = (guessedPerson) => {
    if (isGameWon || !dailyRanking || !guessedPerson) return;

    const result = dailyRanking.get(guessedPerson.qid);
    if (!result) return; // Should not happen if person is from the list

    const newGuesses = [...guesses, result];
    setGuesses(newGuesses.sort((a, b) => a.rank - b.rank));

    if (result.qid === SECRET_PERSON_QID) {
      setIsGameWon(true);
    }
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>PersonaGuess</h1>
        <p>Guess the secret person of the day!</p>
      </header>
      <main>
        {isLoading && <p>Loading game data...</p>}
        {error && <p className="error-message">{error}</p>}
        {isGameWon && <div className="win-message"><h2>Congratulations!</h2><p>You found the secret person: {dailyRanking.get(SECRET_PERSON_QID).label}</p></div>}

        {!isLoading && !error && (
          <>
            <GuessInput allPersons={allPersons} onGuess={handleGuess} disabled={isGameWon} />
            <GuessList guesses={guesses} />
          </>
        )}
      </main>
      <footer className="app-footer">
        <p>Game by Jules</p>
      </footer>
    </div>
  );
}

export default App;