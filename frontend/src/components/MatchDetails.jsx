import React, { useState, useEffect } from 'react';
import axios from 'axios';

const formatPercent = (val) => `${(val * 100).toFixed(1)}%`;

export default function MatchDetails({ sessionId, personQid, personLabel, onClose }) {
  const [matchDetails, setMatchDetails] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showNarrativeDetails, setShowNarrativeDetails] = useState(false);

  useEffect(() => {
    const fetchMatchDetails = async () => {
      console.log('MatchDetails useEffect called with:', { sessionId, personQid, personLabel });
      if (!sessionId || !personQid) {
        console.log('Missing sessionId or personQid');
        return;
      }
      
      try {
        setIsLoading(true);
        const response = await axios.post('/get_match_details', { 
          sessionId, 
          personQid 
        });
        setMatchDetails(response.data.matchDetails);
      } catch (err) {
        setError('Could not fetch match details');
        console.error('Error fetching match details:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchMatchDetails();
  }, [sessionId, personQid]);

  if (isLoading) return <div>Loading match details...</div>;
  if (error) return <div>{error}</div>;
  if (!matchDetails) return null;

  return (
    <div className="match-details-overlay" onClick={onClose}>
      <div className="match-details-modal" onClick={(e) => e.stopPropagation()}>
        <div className="match-details-header">
          <h3>Match Details: {personLabel}</h3>
          <button onClick={onClose} className="close-btn">×</button>
        </div>
        
        <div className="match-details-content">
          <div className="match-section">
            <h4>📖 Narrative Similarity</h4>
            <div className="similarity-display">
              <div className="similarity-bar">
                <div className="bar-bg">
                  <div 
                    className="bar-fill bar-narrative" 
                    style={{width: formatPercent(matchDetails.narrativeSimilarity)}}
                  ></div>
                </div>
                <span className="sim-value">{formatPercent(matchDetails.narrativeSimilarity)}</span>
              </div>
              <p className="similarity-description">
                {matchDetails.narrativeDetails?.explanation || "This measures how similar the narrative descriptions and contexts are between the two persons."}
              </p>
              <button 
                onClick={() => setShowNarrativeDetails(!showNarrativeDetails)}
                className="details-toggle-btn"
              >
                {showNarrativeDetails ? '🔽 Hide Technical Details' : '🔽 Show Technical Details'}
              </button>
              {showNarrativeDetails && matchDetails.narrativeDetails && (
                <div className="technical-details">
                  <div className="detail-grid">
                    <div className="detail-item">
                      <span className="detail-label">Vector Dimensions:</span>
                      <span className="detail-value">{matchDetails.narrativeDetails.vectorDimensions}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Cosine Distance:</span>
                      <span className="detail-value">{matchDetails.narrativeDetails.cosineDistance.toFixed(4)}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Person Vector Magnitude:</span>
                      <span className="detail-value">{matchDetails.narrativeDetails.magnitude1.toFixed(4)}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Secret Vector Magnitude:</span>
                      <span className="detail-value">{matchDetails.narrativeDetails.magnitude2.toFixed(4)}</span>
                    </div>
                  </div>
                  <div className="detail-explanation">
                    <p><strong>How it works:</strong> Narrative similarity uses cosine similarity to measure the angle between high-dimensional vector representations of each person's narrative description. A score closer to 1.0 indicates more similar themes and contexts.</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="match-section">
            <h4>📊 Factual Properties</h4>
            <div className="matches-grid">
              <div className="matches-column">
                <h5>✅ Shared Properties</h5>
                {matchDetails.factualMatches.length > 0 ? (
                  <ul className="match-list">
                    {matchDetails.factualMatches.map((match, index) => (
                      <li key={index} className="match-item positive">{match}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="no-matches">No shared factual properties</p>
                )}
              </div>
              <div className="matches-column">
                <h5>❌ Different Properties</h5>
                {matchDetails.factualNonMatches.length > 0 ? (
                  <ul className="match-list">
                    {matchDetails.factualNonMatches.map((nonMatch, index) => (
                      <li key={index} className="match-item negative">{nonMatch}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="no-matches">No different factual properties</p>
                )}
              </div>
            </div>
          </div>

          <div className="match-section">
            <h4>🔗 Relational Properties</h4>
            <div className="matches-grid">
              <div className="matches-column">
                <h5>✅ Shared Relations</h5>
                {matchDetails.relationalMatches.length > 0 ? (
                  <ul className="match-list">
                    {matchDetails.relationalMatches.map((match, index) => (
                      <li key={index} className="match-item positive">{match}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="no-matches">No shared relational properties</p>
                )}
              </div>
              <div className="matches-column">
                <h5>❌ Different Relations</h5>
                {matchDetails.relationalNonMatches.length > 0 ? (
                  <ul className="match-list">
                    {matchDetails.relationalNonMatches.map((nonMatch, index) => (
                      <li key={index} className="match-item negative">{nonMatch}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="no-matches">No different relational properties</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
