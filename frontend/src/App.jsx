import React, { useState, useEffect } from 'react'; import axios from 'axios'; import GuessInput from './components/GuessInput'; import GuessList from './components/GuessList'; import './App.css';
const API_URL = import.meta.env.PROD ? '' : 'http://localhost:8000'; const SECRET_PERSON_QID = 'Q307';
function App() {
  const [allPersons, setAllPersons] = useState([]); const [dailyRanking, setDailyRanking] = useState(null); const [guesses, setGuesses] = useState([]); const [isGameWon, setIsGameWon] = useState(false); const [isLoading, setIsLoading] = useState(true); const [error, setError] = useState(null);
  useEffect(() => { const fetchGameData = async () => { try { const res = await Promise.all([axios.get(`${API_URL}/persons`), axios.get(`${API_URL}/daily_ranking?secret_qid=${SECRET_PERSON_QID}`)]); setAllPersons(res[0].data); setDailyRanking(new Map(res[1].data.map(p => [p.qid, p]))); } catch (err) { setError("Could not connect to server."); } finally { setIsLoading(false); } }; fetchGameData(); }, []);
  const handleGuess = (person) => { if (isGameWon || !dailyRanking || !person) return; const result = dailyRanking.get(person.qid); if (!result) return; const newGuesses = [...guesses, result]; setGuesses(newGuesses.sort((a, b) => a.rank - b.rank)); if (result.qid === SECRET_PERSON_QID) setIsGameWon(true); };
  return (<div className="app-container"><header className="app-header"><h1>PersonaGuess</h1></header><main>{isLoading ? <p>Loading...</p> : error ? <p>{error}</p> : isGameWon ? <div className="win-message"><h2>Congratulations!</h2><p>You found: {dailyRanking.get(SECRET_PERSON_QID).label}</p></div> : <><GuessInput allPersons={allPersons} onGuess={handleGuess} disabled={isGameWon} /><GuessList guesses={guesses} /></>}</main></div>);
}
export default App;
