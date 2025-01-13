import React, { useState, useRef, useEffect } from 'react';
import { Send } from 'lucide-react';

// Types and Interfaces
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

interface Message {
  type: 'user' | 'assistant';
  content: string;
  results?: SearchResult[];
}

interface ConversationHistory {
  role: string;
  question: string;
  llm_response: string;
}

interface UserRole {
  id: string;
  title: string;
  description: string;
}

const SearchBar = () => {
  // State Management
  const [userRole, setUserRole] = useState('');
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversation, setConversation] = useState<Message[]>([{
    type: 'assistant',
    content: `Welcome to the New England First Amendment Coalition, the region's leading defender of First Amendment freedoms and government transparency. How can I help you?`
  }]);
  const [convoHistory, setConvoHistory] = useState<ConversationHistory[]>([]);

  // Refs
  const conversationEndRef = useRef<HTMLDivElement>(null);

  // Constants
  const userRoles: UserRole[] = [
    {
      id: 'citizen',
      title: 'Private Citizens',
      description: 'Explore the foundations of free speech, press freedom, assembly, and petition rights.',
    },
    {
      id: 'educator',
      title: 'Educators',
      description: 'Assist in teaching the nuances of the First Amendment.',
    },
    {
      id: 'journalist',
      title: 'Journalists',
      description: 'Dive into case studies and legal interpretations concerning freedom of the press.',
    },
    {
      id: 'lawyer',
      title: 'Lawyers',
      description: 'Navigate through precedents and legal arguments related to First Amendment cases.',
    }
  ];

  const suggestionsByRole: {
    [key: string]: string[];
    citizen: string[];
    educator: string[];
    journalist: string[];
    lawyer: string[];
  } = {
    'citizen': [
      "What are my rights under the First Amendment?",
      "How can I protect my free speech rights?",
      "Popular Document: Guide to Free Speech",
      "Popular Document: Citizen's Rights Handbook"
    ],
    'educator': [
      "How can I teach First Amendment rights in school?",
      "What resources exist for teaching about free speech?",
      "Popular Document: Educator's Guide to the First Amendment",
      "Popular Document: Teaching Freedom of Expression"
    ],
    'journalist': [
      "What are the legal protections for journalists?",
      "How can I protect my sources?",
      "Popular Document: Journalists' Legal Rights",
      "Popular Document: Press Freedom in Practice"
    ],
    'lawyer': [
      "What are the latest First Amendment case precedents?",
      "How do I defend First Amendment rights in court?",
      "Popular Document: Landmark First Amendment Cases",
      "Popular Document: Legal Strategies for Free Speech Defense"
    ]
  };
  
  // Helper Functions
  const reformatConvoHistory = (history: ConversationHistory[]): string => {
    return history
      .map(item => `Previous ${item.role} question: ${item.question}\nPrevious Follow Up Question: ${item.llm_response}`)
      .join('\n\n');
  };

  // Effects
  useEffect(() => {
    // Auto-scroll to the latest message
    if (conversationEndRef.current) {
      conversationEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [conversation]);

  // Event Handlers
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  };

  const performSearch = async (searchText: string) => {
    if (!searchText.trim()) return;

    // Update UI to show user message
    setConversation(prev => [...prev, { type: 'user', content: searchText }]);
    setIsLoading(true);

    try {
      // Make API request
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
            prompt: searchText,
            convoHistory: reformatConvoHistory(convoHistory),
            roleFilter: userRole
          }
        }),
      });

      const data = await response.json();
      const results = data.data.askLlm;

      // Handle response based on type
      if (results[0]?.title === "follow-up") {
        // Handle follow-up response
        setConvoHistory(prev => [...prev, { 
          role: 'user', 
          question: searchText, 
          llm_response: results[0].summary 
        }]);
        setConversation(prev => [
          ...prev,
          { type: 'assistant', content: results[0].summary }
        ]);
      } else {
        // Handle search results
        setConversation(prev => [
          ...prev,
          { type: 'assistant', content: "Here's what I found:", results }
        ]);
      }
      setInputValue('');
    } catch (error) {
      console.error(error);
      setConversation(prev => [
        ...prev,
        { type: 'assistant', content: "Sorry, I encountered an error while searching." }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    await performSearch(inputValue);
  };

  const handleSuggestionClick = async (suggestion: string) => {
    await performSearch(suggestion);
  };

  // UI Components
  const RoleSelection = () => (
    <div className="flex flex-col items-center justify-center p-4">
      <h1 className="text-4xl font-bold mb-6 text-blue-700">Choose Your Role</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-7xl">
        {userRoles.map((role) => (
          <button
            key={role.id}
            onClick={() => {
              setUserRole(role.id);
              setConversation([{
                type: 'assistant',
                content: `Welcome to the New England First Amendment Coalition, the region's leading defender of First Amendment freedoms and government transparency. ${role.id ? `I see that you are a${["a","e","i","o","u"].includes(role.id[0]) ? "n" : ""} ${role.id}.` : ''} How can I help you?`
              }]);
            }}
            className="p-6 bg-blue-50 shadow-md rounded-lg transition-transform hover:scale-105"
          >
            <h2 className="text-2xl font-semibold text-gray-800">{role.title}</h2>
            <p className="mt-2 text-sm text-gray-600">{role.description}</p>
          </button>
        ))}
      </div>
    </div>
  );

  const MessageBubble = ({ msg }: { msg: Message }) => (
    <div className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[80%] rounded-lg ${
        msg.type === 'user' ? 'bg-blue-500 text-white' : 'bg-white shadow-md'
      } p-4`}>
        <p className="text-base">{msg.content}</p>
        {msg.results && (
          <div className="mt-4 space-y-4">
            {msg.results.map((result, idx) => (
              <SearchResultItem key={idx} result={result} isUserMessage={msg.type === 'user'} />
            ))}
          </div>
        )}
      </div>
    </div>
  );

  const SearchResultItem = ({ result, isUserMessage }: { result: SearchResult; isUserMessage: boolean }) => (
    <div className="border-t border-gray-200 pt-4">
      <h3 className="font-medium">
        <a
          href={result.link}
          className={`${isUserMessage ? 'text-blue-200' : 'text-blue-600'} hover:underline`}
          target="_blank"
          rel="noopener noreferrer"
        >
          {result.title}
        </a>
      </h3>
      <p className={`mt-2 ${isUserMessage ? 'text-white' : 'text-gray-700'}`}>
        {result.summary}
        {result.citations.map((citation) => (
          <span key={citation.id} className="inline-block mx-1 group relative">
            <span className={isUserMessage ? 'text-blue-200' : 'text-blue-500'}>
              [{citation.id}]
            </span>
            <span className="invisible group-hover:visible absolute bottom-full left-1/2 transform -translate-x-1/2 bg-black text-white text-sm rounded p-2 w-64 z-10">
              {citation.context}
            </span>
          </span>
        ))}
      </p>
    </div>
  );

  // Main Render
  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {userRole === "" ? (
        <RoleSelection />
      ) : (
        <>
          {/* Conversation Container */}
          <div className="flex-1 overflow-y-auto p-4">
            <div className="max-w-4xl mx-auto space-y-4">
              {conversation.map((msg, index) => (
                <MessageBubble key={index} msg={msg} />
              ))}
  
              {/* Initial suggestions */}
              {conversation.length === 1 && (
                <div className="flex justify-center space-x-4 flex-wrap">
                  {suggestionsByRole[userRole] && suggestionsByRole[userRole].map((suggestion, index) => (
                    <button
                      key={index}
                      onClick={() => handleSuggestionClick(suggestion.startsWith('Popular Document:') ? suggestion.slice('Popular Document:'.length) : suggestion)}
                      className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 mb-2"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              )}
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