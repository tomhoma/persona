import React, { useState } from 'react';
export default function GuessInput({ allPersons, onGuess, disabled }) {
  const [val, setVal] = useState(''); const [sugs, setSugs] = useState([]);
  const handleInput = (e) => { const v = e.target.value; setVal(v); if (v.length > 1 && !disabled) { setSugs(allPersons.filter(p => p.label.toLowerCase().includes(v.toLowerCase())).slice(0,10)); } else { setSugs([]); } };
  const handleSelect = (p) => { setVal(''); setSugs([]); onGuess(p); };
  return (<div className="guess-input-container"><input type="text" placeholder={disabled?"You won!":"Enter a name..."} value={val} onChange={handleInput} disabled={disabled} className="guess-input" />{sugs.length>0 && <ul className="autocomplete-suggestions">{sugs.map(p=>(<li key={p.qid} onClick={()=>handleSelect(p)}>{p.label}</li>))}</ul>}</div>);
}
