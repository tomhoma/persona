import React from 'react';

const getRankColor = (rank) => {
  if (rank === 1) return 'rank-gold';
  if (rank <= 300) return 'rank-green';
  if (rank <= 1500) return 'rank-yellow';
  return 'rank-red';
};

const GuessList = ({ guesses }) => {
  return (
    <div className="guess-list-container">
      <div className="guess-list-header">
        <div>Rank</div>
        <div>Name</div>
      </div>
      <div className="guess-list-body">
        {guesses.length === 0 ? (
          <div className="guess-list-empty">Your guesses will appear here.</div>
        ) : (
          guesses.map((guess) => (
            <div
              key={guess.qid}
              className={`guess-list-item ${getRankColor(guess.rank)}`}
            >
              <div className="item-rank">{guess.rank}</div>
              <div className="item-label">{guess.label}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default GuessList;