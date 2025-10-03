import React, { useState } from 'react';

const GuessInput = ({ allPersons, onGuess, disabled }) => {
  const [inputValue, setInputValue] = useState('');
  const [suggestions, setSuggestions] = useState([]);

  const handleInputChange = (e) => {
    const value = e.target.value;
    setInputValue(value);

    if (value.length > 1 && !disabled) {
      const filteredSuggestions = allPersons
        .filter((person) =>
          person.label.toLowerCase().includes(value.toLowerCase())
        )
        .slice(0, 10);
      setSuggestions(filteredSuggestions);
    } else {
      setSuggestions([]);
    }
  };

  const handleSuggestionClick = (person) => {
    setInputValue(''); // Clear input after guess
    setSuggestions([]);
    onGuess(person); // Trigger the guess in the parent component
  };

  return (
    <div className="guess-input-container">
      <input
        type="text"
        placeholder={disabled ? "You found it!" : "Enter a person's name..."}
        className="guess-input"
        value={inputValue}
        onChange={handleInputChange}
        disabled={disabled}
      />
      {suggestions.length > 0 && (
        <ul className="autocomplete-suggestions">
          {suggestions.map((person) => (
            <li key={person.qid} onClick={() => handleSuggestionClick(person)}>
              {person.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default GuessInput;