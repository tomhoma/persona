import React from 'react';
const getRankColor = (r) => { if (r === 1) return 'rank-gold'; if (r <= 300) return 'rank-green'; if (r <= 1500) return 'rank-yellow'; return 'rank-red'; };
export default function GuessList({ guesses }) {
  return (<div className="guess-list-container"><div className="guess-list-header"><div>Rank</div><div>Name</div></div><div className="guess-list-body">{guesses.length===0?(<div className="guess-list-empty">Guesses appear here.</div>):(guesses.map(g=>(<div key={g.qid} className={`guess-list-item ${getRankColor(g.rank)}`}><div className="item-rank">{g.rank}</div><div>{g.label}</div></div>)))}</div></div>);
}
