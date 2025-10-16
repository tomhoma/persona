import React, { useState, useEffect } from 'react';
import axios from 'axios';
import MatchDetails from './MatchDetails';

const formatPercent = (val) => `${(val * 100).toFixed(1)}%`;

export default function TopRelations({ sessionId, secretQid, limit = 10 }) {
  const [dailyRanking, setDailyRanking] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedPerson, setSelectedPerson] = useState(null);

  useEffect(() => {
    const fetchRanking = async () => {
      if (!sessionId) return;
      
      try {
        setIsLoading(true);
        const response = await axios.post('/get_ranking', { sessionId });
        setDailyRanking(response.data.dailyRanking);
      } catch (err) {
        setError('Could not fetch ranking data');
        console.error('Error fetching ranking:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchRanking();
  }, [sessionId]);

  if (isLoading) return <div>Loading relations...</div>;
  if (error) return <div>{error}</div>;
  if (!dailyRanking || !secretQid) return null;
  
  // Get all persons including the secret person, sorted by similarity
  const allPersons = dailyRanking
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);

  if (allPersons.length === 0) return null;

  return (
    <div className="top-relations-container">
      <h3>🔗 Top Relations to Secret Person</h3>
      <div className="top-relations-list">
        {allPersons.map((person, index) => (
          <div key={person.qid} className={`top-relation-item ${person.qid === secretQid ? 'secret-person' : ''}`}>
            <div className="relation-rank">#{index + 1}</div>
            <div className="relation-name">{person.label}</div>
            <div className="relation-scores">
              <div className="similarity-bar">
                <span className="sim-label">📖 Narrative:</span>
                <div className="bar-bg">
                  <div className="bar-fill bar-narrative" style={{width: formatPercent(person.sim_narrative)}}></div>
                </div>
                <span className="sim-value">{formatPercent(person.sim_narrative)}</span>
              </div>
              <div className="similarity-bar">
                <span className="sim-label">📊 Factual:</span>
                <div className="bar-bg">
                  <div className="bar-fill bar-factual" style={{width: formatPercent(person.sim_factual)}}></div>
                </div>
                <span className="sim-value">{formatPercent(person.sim_factual)}</span>
              </div>
              <div className="similarity-bar">
                <span className="sim-label">🔗 Relational:</span>
                <div className="bar-bg">
                  <div className="bar-fill bar-relational" style={{width: formatPercent(person.sim_relational)}}></div>
                </div>
                <span className="sim-value">{formatPercent(person.sim_relational)}</span>
              </div>
              <div className="similarity-total">
                <strong>Total: {person.score.toFixed(4)}</strong>
              </div>
            </div>
            <div className="relation-actions">
              <button 
                onClick={() => {
                  console.log('Details button clicked for:', person.label);
                  setSelectedPerson(person);
                }}
                className="details-btn"
                title="View detailed match information"
              >
                🔍 Details
              </button>
            </div>
          </div>
        ))}
      </div>
      
      {selectedPerson && (
        <MatchDetails
          sessionId={sessionId}
          personQid={selectedPerson.qid}
          personLabel={selectedPerson.label}
          onClose={() => setSelectedPerson(null)}
        />
      )}
    </div>
  );
}
