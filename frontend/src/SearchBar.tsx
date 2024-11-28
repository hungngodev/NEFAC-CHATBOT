import React, { useState, useRef, useEffect } from 'react';
import { Search, Send } from 'react-feather';

const SearchBar = () => {
  const [inputValue, setInputValue] = useState('');
  const [conversation, setConversation] = useState<{ type: string; content: string; source?: string }[]>([]);
  const conversationEndRef = useRef<HTMLDivElement>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  };

  // Hook to scroll the container to the bottom whenever the conversation array changes.
  useEffect(() => {
    if (conversationEndRef.current) {
      conversationEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [conversation]);


  const handleSearch = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (inputValue.trim().length === 0) {
      return; // Exit the function if input is empty or only whitespace
    }
    setConversation(prev => [...prev, { type: 'user', content: inputValue }]);
    setInputValue('');
    console.log(inputValue);
    try {
      const response = await fetch('http://127.0.0.1:8000/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: `
            query {
              askLlm(prompt: "${inputValue}")
            }
          `,
        }),
      });
      const result = await response.json();
      const { data } = result; // Destructure result
      const { askLlm } = data; // Destructure data

      setConversation(prev => [...prev, { type: 'ai', content: askLlm }]);
    } catch (e) {
      console.log(e);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen ">
      {/* Exit button "Set conversation to empty" */}
      {conversation.length > 0? 
        <button onClick={() => {setConversation([])}} className='fixed top-10 left-10 border border-gray-950 p-2 rounded-xl w-auto'>
          Exit
        </button>: null
      }
      <div 
        className={`flex flex-col border border-neutral-300 items-center rounded-2xl justify-center w-auto bg-white shadow-md p-4 transition-all duration-500 ease-in-out mb-5 ${conversation.length > 0 ? 'fixed bottom-0' : 'relative top-1/2 transform -translate-y-1/2'}`}>
        <form onSubmit={handleSearch} className="flex gap-2 mb-1">
          <input
            type="search"
            placeholder={conversation.length > 0? "Ask follow-up" : "Search"}
            value={inputValue}
            onChange={handleInputChange}
            className="w-96 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button type="submit" className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
            <Send className="inline-block h-5 w-5" />
          </button>
        </form>
      </div>

      <div className="w-full max-w-lg mb-20 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 150px)' }}>
        {conversation.map((msg, index) => (
          <React.Fragment key={index}>
            <div className={`p-4 my-2 rounded-lg ${msg.type === 'user' ? 'text-2xl' : 'bg-gray-100 text-base'}`}>
              <p>{msg.content}</p>
              {msg.source && (
                <p className="text-sm text-blue-500">
                  Source: <a href={msg.source} target="_blank" rel="noopener noreferrer">{msg.source}</a>
                </p>
              )}
            </div>
            {msg.type === 'ai' && index < conversation.length - 1 && <hr className="my-4 border-t border-gray-300" />}
          </React.Fragment>
        ))}
        <div ref={conversationEndRef} />
      </div>
    </div>
  );
};

export default SearchBar;