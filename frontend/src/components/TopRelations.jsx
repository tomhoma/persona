import React from 'react';

const formatPercent = (val) => `${(val * 100).toFixed(1)}%`;

export default function TopRelations({ dailyRanking, secretQid, limit = 10 }) {
  if (!dailyRanking || !secretQid) return null;
  
  // Get all persons including the secret person, sorted by similarity
  const allPersons = Array.from(dailyRanking.values())
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
          </div>
        ))}
      </div>
    </div>
  );
}
