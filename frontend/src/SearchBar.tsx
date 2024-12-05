import React, { useState, useRef, useEffect } from 'react';
import { Search, Send } from 'react-feather';

const SearchBar = () => {

      const [userRole, setUserRole] = useState('');
      const [inputValue, setInputValue] = useState('');
      const [conversation, setConversation] = useState<{ type: string; content: string; source?: string }[]>([]);
      const conversationEndRef = useRef<HTMLDivElement>(null);

      const userRoles = [
        {
          id: 'citizen',
          title: 'Private Citizens',
          description: 'Explore the foundations of free speech, press freedom, assembly, and petition rights. Understand how these rights affect your daily life and learn how to engage with them effectively.'
        },
        {
          id: 'educator',
          title: 'Educators',
          description: 'Assist in teaching the nuances of the First Amendment. Access historical documents, court decisions, and educational resources to enhance curriculum on civil liberties and constitutional rights.'
        },
        {
          id: 'journalist',
          title: 'Journalists',
          description: 'Dive into case studies, legal interpretations, and landmark decisions concerning freedom of the press. Use this tool to investigate how journalism is protected and what boundaries exist within First Amendment law.'
        },
        {
          id: 'lawyer',
          title: 'Lawyers',
          description: 'Navigate through precedents, legal arguments, and current issues related to First Amendment cases. Utilize this bot for quick legal research, client counseling, or preparing for litigation involving free speech, religion, or assembly rights.'
        }
      ];
  
    
  useEffect(() => {
    if (conversationEndRef.current) {
      conversationEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [conversation]);

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      setInputValue(e.target.value);
    };
  const handleSearch = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
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
      <div className="flex flex-col items-center justify-center min-h-screen bg-white" style={{ backgroundImage: "linear-gradient(to bottom, rgba(255,255,255,0.8), rgba(255,255,255,0.8))", backgroundSize: 'cover' }}>
      {/* Role Selection */}
      {userRole === "" && (
        <div className="flex flex-col items-center justify-center px-4 md:px-6 lg:px-8" style={{ minHeight: '100vh' }}>
        <h1 className="text-4xl font-bold mb-6 text-blue-700">Choose Your Role</h1>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4 max-w-7xl mx-auto">
          {userRoles.map((role) => (
            <button 
              key={role.id}
              onClick={() => setUserRole(role.id)}
              className="p-6 bg-blue-100 shadow-md hover:shadow-lg rounded-lg transform transition-transform duration-300 hover:scale-105 focus:outline-none"
              style={{backgroundColor: 'rgb(239, 246, 255)'}}>
              <h2 className="text-2xl font-semibold text-black-800">{role.title}</h2>
              <p className="mt-2 font-semibold text-sm text-black-800">{role.description}</p>
            </button>
          ))}
        </div>
      </div>
      )}
      
      {/* Exit and Edit Role Buttons */}
      {conversation.length > 0 && userRole !== "" && (
        <button onClick={() => setConversation([])} className="fixed top-10 left-10 bg-white text-blue-500 border-2 border-blue-500 px-4 py-2 rounded-full shadow-lg hover:bg-blue-500 hover:text-white transition-colors duration-200">
          Exit
        </button>
      )}

      {userRole !== "" && (
        <button onClick={() => setUserRole("")} className="fixed top-10 right-10 bg-white text-blue-500 border-2 border-blue-500 px-4 py-2 rounded-full shadow-lg hover:bg-blue-500 hover:text-white transition-colors duration-200">
          Edit Role
        </button>
      )}

      <div className={` flex flex-col border border-neutral-300 items-center rounded-2xl justify-center w-auto bg-white shadow-md p-4 transition-all duration-500 ease-in-out mb-5 ${conversation.length > 0 ? 'fixed bottom-0' : 'relative top-1/2 transform -translate-y-1/2'}`}>
        <form onSubmit={handleSearch} className="flex gap-2 mb-1">
          <input
            type="search"
            placeholder={conversation.length > 0? "Ask follow-up" : "Search"}
            value={inputValue}
            onChange={handleInputChange}
            className="w-96 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button type="submit" className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
            <Send className="inline-block  h-5 w-5" />
          </button>
        </form>
      </div>

      <div className="w-full max-w-lg mb-20">
        {conversation.map((msg, index) => (
          <React.Fragment key={index}>
            <div className={`p-4 my-2 rounded-lg ${msg.type === 'user' ? ' text-2xl ' : 'bg-gray-100 text-base'}`}>
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
      </div>
      <div ref={conversationEndRef} />
    </div>
  );
};

export default SearchBar;