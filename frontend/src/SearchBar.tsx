import React, { useState, useRef, useEffect } from 'react';
import { Search, Send } from 'lucide-react';

interface Citation {
  id: string;
  context: string;
}

interface SearchResult {
  title: string;
  link: string;
  summary: string;
  citations: Citation[];
}

const SearchBar = () => {

      const [userRole, setUserRole] = useState('');
      const [contentType, setContentType] = useState('');
      const [resourceType, setResourceType] = useState('');
      const [inputValue, setInputValue] = useState('');
      const [conversation, setConversation] = useState<{ type: string; content: string; source?: string }[]>([]);
      const conversationEndRef = useRef<HTMLDivElement>(null);

      const [results, setResults] = useState<SearchResult[]>([]);
      const [isLoading, setIsLoading] = useState(false);
      
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
      setIsLoading(true);
      try {
        const response = await fetch('http://127.0.0.1:8000/graphql', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            query: `
            query Search($prompt: String!) {
              askLlm(prompt: $prompt, roleFilter: "${userRole}", contentType: "${contentType}", resourceType: "${resourceType}") {
                title
                link
                summary
                citations {
                  id
                  context
                }
              }
            }
          `,
          variables: {
            prompt: inputValue,
            convoHistory: reformatConvoHistory(convoHistory),
            roleFilter: userRole
          }
        }),
      });

      const data = await response.json();
      const results = data.data.askLlm;

      if (results[0]?.title === "follow-up") {
        setConvoHistory([...convoHistory, { role: 'user', question: inputValue, llm_response: results[0].summary }]);
        setConversation([
          ...conversation,
          { type: 'user', content: inputValue },
          { type: 'assistant', content: results[0].summary }
        ]);
      } else {
        setConversation([
          ...conversation,
          { type: 'user', content: inputValue },
          { type: 'assistant', content: "Here's what I found:", results }
        ]);
      }
      setInputValue('');
    } catch (error) {
      console.error(error);
      setConversation([
        ...conversation,
        { type: 'user', content: inputValue },
        { type: 'assistant', content: "Sorry, I encountered an error while searching." }
      ]);
    } finally {
      setIsLoading(false);
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
      </div> )
      }
      
    {/* Edit Role and Dropdowns */}
      {/* First Dropdown */}
      {userRole !== "" && (
        <div className="fixed top-10 right-10 flex items-center space-x-4">
        <select 
        className="bg-white text-blue-500 border-2 border-blue-500 px-4 py-2 rounded-full shadow-lg hover:bg-blue-500 hover:text-white transition-colors duration-200"
        onChange={(e) => {
            setResourceType(e.target.value);
        }}
        >
          <option value="">Select Resource Type</option>
          <option value="option1">Guides</option>
          <option value="option2">Lessons</option>
          <option value="option3">Multimedia</option>
        </select>

        {/* Second Dropdown */}
        <select 
            className="bg-white text-blue-500 border-2 border-blue-500 px-4 py-2 rounded-full shadow-lg hover:bg-blue-500 hover:text-white transition-colors duration-200"
            onChange={(e) => {
            setContentType(e.target.value);
          }}
        >
          <option value="">Select Content Type </option>
          <option value="option1">Advocacy</option>
          <option value="option2">Civic Education</option>
          <option value="option3">Community Outreach</option>
          <option value="option4">First Amendment Rights</option>
          <option value="option5">Government Transparency</option>
          <option value="option6">Investigative Journalism</option>
          <option value="option7">Media Law</option>
          <option value="option8">Mentorship</option>
          <option value="option9">Open Meeting Law</option>
          <option value="option10">Public Records Law</option>
          <option value="option11">Skill Building</option>
          <option value="option12">Workshops</option>
        </select>

        {/* Edit Role Button */}
        <button 
          onClick={() => setUserRole("")} 
          className="bg-white text-blue-500 border-2 border-blue-500 px-4 py-2 rounded-md shadow-lg hover:bg-blue-500 hover:text-white transition-colors duration-200"
        >
          Edit Role
        </button>
      </div> )
      }

      {/* <div className="w-full max-w-lg mb-20">
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
        ))} */}
            {/* Results Listing */}

    {/* Loading Indicator */}
    {isLoading && (
      <div className="flex justify-center items-center my-4">
        <svg
          className="animate-spin h-8 w-8 text-blue-500"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          ></circle>
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8v8H4z"
          ></path>
        </svg>
        <span className="ml-2 text-blue-500">Searching...</span>
      </div> )
    }

  {/* Results */}
  {!isLoading && results.length > 0 && (<div className="space-y-6" >
    {results.map((result, index) => (
      <div key={index} className="border rounded-lg p-6 hover:shadow-lg transition-shadow">
        <h2 className="text-xl font-semibold mb-2">
          <a
            href={result.link}
            className="text-blue-600 hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            {result.title}
          </a>
        </h2>
        <p className="text-gray-700">
          {result.summary}
          {result.citations.map(citation => (
            <span
              key={citation.id}
              className="inline-block mx-1 cursor-help relative group"
            >
              <span className="text-blue-500">[{citation.id}]</span>
              <span className="invisible group-hover:visible absolute bottom-full left-1/2 transform -translate-x-1/2 bg-black text-white text-sm rounded p-2 w-64">
                {citation.context}
              </span>
            </span>
          ))}
        </p>
      </div>
    ))}
  </div>)}

  {/* Search Bar */}
  <div className="fixed bottom-0 left-0 right-0 flex justify-center items-end h-20 bg-white z-10">
    <form onSubmit={handleSearch} className="w-full max-w-md mb-4">
      <div className="flex items-end justify-center">
        <input
          type="search"
          placeholder="Search"
          value={inputValue}
          onChange={handleInputChange}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="submit"
          className="ml-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          Search
        </button>
      </div>
    </form>
  </div>
  </div>
  );
};

export default SearchBar;