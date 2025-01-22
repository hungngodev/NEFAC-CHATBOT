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
  const [contentType, setContentType] = useState('');
  const [resourceType, setResourceType] = useState('');
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversation, setConversation] = useState<Message[]>([{
    type: 'assistant',
    content: `Welcome to the New England First Amendment Coalition, the region's leading defender of First Amendment freedoms and government transparency. How can I help you?`
  }]);
  const [convoHistory, setConvoHistory] = useState<ConversationHistory[]>([]);

  // Refs
  const conversationEndRef = useRef<HTMLDivElement>(null);

  // Effects
  useEffect(() => {
    if (conversationEndRef.current) {
      conversationEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [conversation]);

  // Event Handlers
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  };

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

  const popularDocumentsByRole: {
    [key: string]: Array<{
      title: string;
      link: string;
      summary: string;
    }>;
  } = {
    'citizen': [
      {
        title: "NEFAC Mentors",
        link: "/docs/by_audience/citizen/NEFAC_Mentors.pdf",
        summary: "The New England First Amendment Coalition offers a mentorship program designed for journalists in the six New England states, connecting them with seasoned professionals for guidance in various journalism skills. Mentors, who commit to at least an hour per month for six months and cover areas from investigative journalism to career development and community storytelling."
      },
      {
        title: "NEFAC Mentors",
        link: "/docs/by_audience/citizen/NEFAC_Mentors.pdf",
        summary: "The New England First Amendment Coalition offers a mentorship program designed for journalists in the six New England states, connecting them with seasoned professionals for guidance in various journalism skills. Mentors, who commit to at least an hour per month for six months and cover areas from investigative journalism to career development and community storytelling."
      }
    ],
    'educator': [
      {
        title: "NEFAC Mentors",
        link: "/docs/by_audience/citizen/NEFAC_Mentors.pdf",
        summary: "The New England First Amendment Coalition offers a mentorship program designed for journalists in the six New England states, connecting them with seasoned professionals for guidance in various journalism skills. Mentors, who commit to at least an hour per month for six months and cover areas from investigative journalism to career development and community storytelling."
      },
      {
        title: "NEFAC Mentors",
        link: "/docs/by_audience/citizen/NEFAC_Mentors.pdf",
        summary: "The New England First Amendment Coalition offers a mentorship program designed for journalists in the six New England states, connecting them with seasoned professionals for guidance in various journalism skills. Mentors, who commit to at least an hour per month for six months and cover areas from investigative journalism to career development and community storytelling."
      }
    ],
    'journalist': [
      {
        title: "Federal FOIA Video Tutorials",
        link: "/docs/by_audience/journalist/Federal_FOIA_%20Video_Tutorials.pdf",
        summary: "Learn about the Freedom of Information Act with video lessons led by experts like Michael Morisy of MuckRock and Erin Siegal McIntyre. These tutorials cover everything from FOIA basics to appealing denied requests, offering practical insights for journalists and researchers."
      },
      {
        title: "FOI Access to State Courts",
        link: "/docs/by_audience/journalist/FOI_Access_to_State_Courts.pdf",
        summary: "Explore how to navigate Massachusetts state courts with our video series. Featuring educators like Ruth Bourquin from the ACLU, Bob Ambrogi from the Massachusetts Newspaper Publishers Association, and Todd Wallack from WBUR, these lessons guide you through accessing court documents, understanding court hearings, and using online judicial resources."
      }
    ],
    'lawyer': [
      {
        title: "NEFAC Mentors",
        link: "/docs/by_audience/citizen/NEFAC_Mentors.pdf",
        summary: "The New England First Amendment Coalition offers a mentorship program designed for journalists in the six New England states, connecting them with seasoned professionals for guidance in various journalism skills. Mentors, who commit to at least an hour per month for six months and cover areas from investigative journalism to career development and community storytelling."
      },
      {
        title: "NEFAC Mentors",
        link: "/docs/by_audience/citizen/NEFAC_Mentors.pdf",
        summary: "The New England First Amendment Coalition offers a mentorship program designed for journalists in the six New England states, connecting them with seasoned professionals for guidance in various journalism skills. Mentors, who commit to at least an hour per month for six months and cover areas from investigative journalism to career development and community storytelling."
      }
    ]
  };

  const suggestionsByRole: {
    [key: string]: string[];
    citizen: string[];
    educator: string[];
    journalist: string[];
    lawyer: string[];
  } = {
    'citizen': [
      "Popular Document: "+popularDocumentsByRole['citizen'][0].title,
      "Popular Document: "+popularDocumentsByRole['citizen'][1].title,
      "What are my rights under the First Amendment?",
      "How can I protect my free speech rights?"
    ],
    'educator': [
      "Popular Document: "+popularDocumentsByRole['educator'][0].title,
      "Popular Document: "+popularDocumentsByRole['citizen'][1].title,
      "How can I teach First Amendment rights in school?",
      "What resources exist for teaching about free speech?"
    ],
    'journalist': [
      "Popular Document: "+popularDocumentsByRole['journalist'][0].title,
      "Popular Document: "+popularDocumentsByRole['journalist'][1].title,
      "What are the legal protections for journalists?",
      "How can I protect my sources?"
    ],
    'lawyer': [
      "Popular Document: "+popularDocumentsByRole['lawyer'][0].title,
      "Popular Document: "+popularDocumentsByRole['lawyer'][1].title,
      "What are the latest First Amendment case precedents?",
      "How do I defend First Amendment rights in court?"
    ]
  };

  // Helper Functions
  const reformatConvoHistory = (history: ConversationHistory[]): string => {
    return history
      .map(item => `Previous ${item.role} question: ${item.question}\nPrevious Follow Up Question: ${item.llm_response}`)
      .join('\n\n');
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
            query Search($prompt: String!, $convoHistory: String!, $roleFilter: String!, $contentType: String, $resourceType: String) {
              askLlm(prompt: $prompt, convoHistory: $convoHistory, roleFilter: $roleFilter, contentType: $contentType, resourceType: $resourceType) {
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
            roleFilter: userRole,
            contentType: contentType,
            resourceType: resourceType
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
    const toSearch=inputValue;
    setInputValue('');
    await performSearch(toSearch);
  };

  const handleSuggestionClick = async (suggestion: string, index:number) => {
    if (suggestion.startsWith("Popular Document:")) {
      setConversation(prev => [
        ...prev,
        { type: 'user', content: suggestion },
        { type: 'assistant', content: "Here's what I found:",  results: [
          {
            title: popularDocumentsByRole[userRole][index].title,
            link: "http://localhost:5173"+popularDocumentsByRole[userRole][index].link,
            summary: popularDocumentsByRole[userRole][index].summary,
            citations: []
          }
        ]}
      ]);
    } else {
      await performSearch(suggestion);
    }
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

  const SuggestionButton = ({ suggestion, index }: { suggestion: string; index: number  }) => {    
    return (
      <button
        onClick={() => handleSuggestionClick(suggestion, index)}
        className="
          w-64
          h-16
          px-6
          py-3
          bg-white/20 
          backdrop-blur-sm
          border
          border-white/30
          text-blue-600
          rounded-xl
          transition-all
          duration-200
          hover:bg-white/30
          hover:border-white/50
          hover:transform
          hover:scale-105
          focus:outline-none
          focus:ring-2
          focus:ring-blue-400
          focus:ring-opacity-50
          shadow-lg
          text-sm
          font-medium
          whitespace-normal
          line-clamp-2
          flex
          items-center
          justify-center
          text-center
        "
      >
        {suggestion}
      </button>
    );
  };

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
    <div className="flex flex-col min-h-screen bg-gray-50">
      {userRole === "" ? (
        <RoleSelection />
      ) : (
        <div>
          {/* Edit Role and Dropdowns */}
          <div className="fixed top-4 right-4 flex flex-col items-end space-y-2">
            <button 
              onClick={() => setUserRole("")} 
              className="bg-blue-500 text-white border-2 border-blue-500 px-4 py-2 rounded-md shadow-lg hover:shadow-xl"
            >
              Edit Role
            </button>
            <select 
              className="bg-white text-blue-500 border-2 border-blue-500 px-4 py-2 rounded-full shadow-lg focus:bg-white focus:text-blue-500"
              onChange={(e) => {
                setResourceType(e.target.value);
              }}
            >
              <option value="">Select Resource Type</option>
              <option value="option1">Guides</option>
              <option value="option2">Lessons</option>
              <option value="option3">Multimedia</option>
            </select>
            <select 
              className="bg-white text-blue-500 border-2 border-blue-500 px-4 py-2 rounded-full shadow-lg focus:bg-white focus:text-blue-500"
              onChange={(e) => {
                setContentType(e.target.value);
              }}
            >
              <option value="">Select Content Type</option>
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
          </div>

          {/* Conversation Container */}
          <div className="flex-1 overflow-y-auto p-4" style={{ marginBottom: '80px' }}>
            <div className="max-w-4xl mx-auto space-y-4">
              {conversation.map((msg, index) => (
                <MessageBubble key={index} msg={msg} />
              ))}
  
              {/* Initial suggestions */}
              {conversation.length === 1 && (
                <div className="fixed bottom-24 left-1/2 -translate-x-1/2 w-full max-w-3xl px-4 py-6 flex flex-wrap justify-center gap-4 z-10">
                  {suggestionsByRole[userRole]?.map((suggestion, index) => (
                    <SuggestionButton suggestion={suggestion} index={index} />
                  ))}
                </div>
              )}
              <div ref={conversationEndRef} />
              </div>
          </div>
  
          {/* Search Input */}
          <div className="p-4 border-t bg-white fixed bottom-0 w-full z-20">
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
        </div>
      )}
    </div>
  );
};

export default SearchBar;