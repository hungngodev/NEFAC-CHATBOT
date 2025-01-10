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
  const [inputValue, setInputValue] = useState('');
  const [conversation, setConversation] = useState<{
    type: 'user' | 'assistant';
    content: string;
    results?: SearchResult[];
  }[]>([{type: 'assistant', content: 'Welcome to the New England First Amendment Coalition, the regions leading defender of First Amendment freedoms and government transparency. How can I help you?'}]);
  const conversationEndRef = useRef<HTMLDivElement>(null);
  const [convoHistory, setConvoHistory] = useState<{ role: string; question: string; llm_response: string }[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const userRoles = [
    {
      id: 'citizen',
      title: 'Private Citizens',
      description: 'Explore the foundations of free speech, press freedom, assembly, and petition rights.'
    },
    {
      id: 'educator',
      title: 'Educators',
      description: 'Assist in teaching the nuances of the First Amendment.'
    },
    {
      id: 'journalist',
      title: 'Journalists',
      description: 'Dive into case studies and legal interpretations concerning freedom of the press.'
    },
    {
      id: 'lawyer',
      title: 'Lawyers',
      description: 'Navigate through precedents and legal arguments related to First Amendment cases.'
    }
  ];

  const reformatConvoHistory = (convoHistory: { role: string; question: string; llm_response: string }[]) => {
    return convoHistory
      .map((item) => `Previous ${item.role} question: ${item.question}\nPrevious Follow Up Question: ${item.llm_response}`)
      .join('\n\n');
  };

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
    if (!inputValue.trim()) return;

    setConversation([...conversation, { type: 'user', content: inputValue }]);
    setIsLoading(true);

    try {
      const response = await fetch('http://127.0.0.1:8000/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: `
            query Search($prompt: String!, $convoHistory: String!, $roleFilter: String!) {
              askLlm(prompt: $prompt, convoHistory: $convoHistory, roleFilter: $roleFilter) {
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
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Role Selection */}
      {userRole === "" && (
        <div className="flex flex-col items-center justify-center p-4">
          <h1 className="text-4xl font-bold mb-6 text-blue-700">Choose Your Role</h1>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-7xl">
            {userRoles.map((role) => (
              <button
                key={role.id}
                onClick={() => setUserRole(role.id)}
                className="p-6 bg-blue-50 shadow-md rounded-lg transition-transform hover:scale-105"
              >
                <h2 className="text-2xl font-semibold text-gray-800">{role.title}</h2>
                <p className="mt-2 text-sm text-gray-600">{role.description}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {userRole !== "" && (
        <>
          {/* Conversation Container */}
          <div className="flex-1 overflow-y-auto p-4">
            <div className="max-w-4xl mx-auto space-y-4">
              {conversation.map((msg, index) => (
                <div
                  key={index}
                  className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg ${
                      msg.type === 'user'
                        ? 'bg-blue-500 text-white'
                        : 'bg-white shadow-md'
                    } p-4`}
                  >
                    <p className="text-base">{msg.content}</p>
                    {msg.results && (
                      <div className="mt-4 space-y-4">
                        {msg.results.map((result, idx) => (
                          <div key={idx} className="border-t border-gray-200 pt-4">
                            <h3 className="font-medium">
                              <a
                                href={result.link}
                                className={`${msg.type === 'user' ? 'text-blue-200' : 'text-blue-600'} hover:underline`}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                {result.title}
                              </a>
                            </h3>
                            <p className={`mt-2 ${msg.type === 'user' ? 'text-white' : 'text-gray-700'}`}>
                              {result.summary}
                              {result.citations.map((citation) => (
                                <span
                                  key={citation.id}
                                  className="inline-block mx-1 group relative"
                                >
                                  <span className={msg.type === 'user' ? 'text-blue-200' : 'text-blue-500'}>
                                    [{citation.id}]
                                  </span>
                                  <span className="invisible group-hover:visible absolute bottom-full left-1/2 transform -translate-x-1/2 bg-black text-white text-sm rounded p-2 w-64 z-10">
                                    {citation.context}
                                  </span>
                                </span>
                              ))}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              <div ref={conversationEndRef} />
            </div>
          </div>

          {/* Search Input */}
          <div className="p-4 border-t bg-white">
            <form onSubmit={handleSearch} className="max-w-4xl mx-auto flex gap-2">
              <input
                type="text"
                value={inputValue}
                onChange={handleInputChange}
                placeholder="Ask a question..."
                className="flex-1 p-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={isLoading}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
              >
                {isLoading ? (
                  <div className="w-6 h-6 border-t-2 border-white rounded-full animate-spin" />
                ) : (
                  <Send className="w-6 h-6" />
                )}
              </button>
            </form>
          </div>
        </>
      )}
    </div>
  );
};

export default SearchBar;