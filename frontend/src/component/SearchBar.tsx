import React, { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import "./SearchBar.css";

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
  type: "user" | "assistant";
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

const BASE_URL = "http://127.0.0.1:8000/graphql";

const SearchBar = () => {
  // State Management
  const [userRole, setUserRole] = useState("");
  const [contentType, setContentType] = useState("");
  const [resourceType, setResourceType] = useState("");
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversation, setConversation] = useState<Message[]>([
    {
      type: "assistant",
      content: `Welcome to the New England First Amendment Coalition, the region's leading defender of First Amendment freedoms and government transparency. How can I help you?`,
    },
  ]);
  const [convoHistory, setConvoHistory] = useState<ConversationHistory[]>([]);
  const prevLength = useRef<number>(1);

  // Refs
  const conversationEndRef = useRef<HTMLDivElement>(null);

  // Effects
  useEffect(() => {
    if (conversationEndRef.current) {
      conversationEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [conversation]);

  // Event Handlers
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  };

  // Constants
  const userRoles: UserRole[] = [
    {
      id: "citizen",
      title: "Private Citizens",
      description:
        "Explore the foundations of free speech, press freedom, assembly, and petition rights.",
    },
    {
      id: "educator",
      title: "Educators",
      description: "Assist in teaching the nuances of the First Amendment.",
    },
    {
      id: "journalist",
      title: "Journalists",
      description:
        "Dive into case studies and legal interpretations concerning freedom of the press.",
    },
    {
      id: "lawyer",
      title: "Lawyers",
      description:
        "Navigate through precedents and legal arguments related to First Amendment cases.",
    },
  ];

  const popularDocumentsByRole: {
    [key: string]: Array<{
      title: string;
      link: string;
      summary: string;
    }>;
  } = {
    citizen: [
      {
        title: "NEFAC Mentors",
        link: "/docs/by_audience/citizen/NEFAC_Mentors.pdf",
        summary:
          "The New England First Amendment Coalition offers a mentorship program designed for journalists in the six New England states, connecting them with seasoned professionals for guidance in various journalism skills. Mentors, who commit to at least an hour per month for six months and cover areas from investigative journalism to career development and community storytelling.",
      },
      {
        title: "NEFAC Mentors",
        link: "/docs/by_audience/citizen/NEFAC_Mentors.pdf",
        summary:
          "The New England First Amendment Coalition offers a mentorship program designed for journalists in the six New England states, connecting them with seasoned professionals for guidance in various journalism skills. Mentors, who commit to at least an hour per month for six months and cover areas from investigative journalism to career development and community storytelling.",
      },
    ],
    educator: [
      {
        title: "NEFAC Mentors",
        link: "/docs/by_audience/citizen/NEFAC_Mentors.pdf",
        summary:
          "The New England First Amendment Coalition offers a mentorship program designed for journalists in the six New England states, connecting them with seasoned professionals for guidance in various journalism skills. Mentors, who commit to at least an hour per month for six months and cover areas from investigative journalism to career development and community storytelling.",
      },
      {
        title: "NEFAC Mentors",
        link: "/docs/by_audience/citizen/NEFAC_Mentors.pdf",
        summary:
          "The New England First Amendment Coalition offers a mentorship program designed for journalists in the six New England states, connecting them with seasoned professionals for guidance in various journalism skills. Mentors, who commit to at least an hour per month for six months and cover areas from investigative journalism to career development and community storytelling.",
      },
    ],
    journalist: [
      {
        title: "Federal FOIA Video Tutorials",
        link: "/docs/by_audience/journalist/Federal_FOIA_%20Video_Tutorials.pdf",
        summary:
          "Learn about the Freedom of Information Act with video lessons led by experts like Michael Morisy of MuckRock and Erin Siegal McIntyre. These tutorials cover everything from FOIA basics to appealing denied requests, offering practical insights for journalists and researchers.",
      },
      {
        title: "FOI Access to State Courts",
        link: "/docs/by_audience/journalist/FOI_Access_to_State_Courts.pdf",
        summary:
          "Explore how to navigate Massachusetts state courts with our video series. Featuring educators like Ruth Bourquin from the ACLU, Bob Ambrogi from the Massachusetts Newspaper Publishers Association, and Todd Wallack from WBUR, these lessons guide you through accessing court documents, understanding court hearings, and using online judicial resources.",
      },
    ],
    lawyer: [
      {
        title: "NEFAC Mentors",
        link: "/docs/by_audience/citizen/NEFAC_Mentors.pdf",
        summary:
          "The New England First Amendment Coalition offers a mentorship program designed for journalists in the six New England states, connecting them with seasoned professionals for guidance in various journalism skills. Mentors, who commit to at least an hour per month for six months and cover areas from investigative journalism to career development and community storytelling.",
      },
      {
        title: "NEFAC Mentors",
        link: "/docs/by_audience/citizen/NEFAC_Mentors.pdf",
        summary:
          "The New England First Amendment Coalition offers a mentorship program designed for journalists in the six New England states, connecting them with seasoned professionals for guidance in various journalism skills. Mentors, who commit to at least an hour per month for six months and cover areas from investigative journalism to career development and community storytelling.",
      },
    ],
  };

  const suggestionsByRole: {
    [key: string]: string[];
    citizen: string[];
    educator: string[];
    journalist: string[];
    lawyer: string[];
  } = {
    citizen: [
      "Popular Document: " + popularDocumentsByRole["citizen"][0].title,
      "Popular Document: " + popularDocumentsByRole["citizen"][1].title,
      "What are my rights under the First Amendment?",
      "How can I protect my free speech rights?",
    ],
    educator: [
      "Popular Document: " + popularDocumentsByRole["educator"][0].title,
      "Popular Document: " + popularDocumentsByRole["citizen"][1].title,
      "How can I teach First Amendment rights in school?",
      "What resources exist for teaching about free speech?",
    ],
    journalist: [
      "Popular Document: " + popularDocumentsByRole["journalist"][0].title,
      "Popular Document: " + popularDocumentsByRole["journalist"][1].title,
      "What are the legal protections for journalists?",
      "How can I protect my sources?",
    ],
    lawyer: [
      "Popular Document: " + popularDocumentsByRole["lawyer"][0].title,
      "Popular Document: " + popularDocumentsByRole["lawyer"][1].title,
      "What are the latest First Amendment case precedents?",
      "How do I defend First Amendment rights in court?",
    ],
  };

  const contentAndResourceTypes = [
    {
      options: [
        { value: "", label: "Select Resource Type" },
        { value: "Guides", label: "Guides" },
        { value: "Lessons", label: "Lessons" },
        { value: "Multimedia", label: "Multimedia" },
      ],
    },
    {
      options: [
        { value: "", label: "Select Content Type" },
        { value: "Advocacy", label: "Advocacy" },
        { value: "Civic Education", label: "Civic Education" },
        { value: "Community Outreach", label: "Community Outreach" },
        { value: "First Amendment Rights", label: "First Amendment Rights" },
        { value: "Government Transparency", label: "Government Transparency" },
        {
          value: "Investigative Journalism",
          label: "Investigative Journalism",
        },
        { value: "Media Law", label: "Media Law" },
        { value: "Mentorship", label: "Mentorship" },
        { value: "Open Meeting Law", label: "Open Meeting Law" },
        { value: "Public Records Law", label: "Public Records Law" },
        { value: "Skill Building", label: "Skill Building" },
        { value: "Workshops", label: "Workshops" },
      ],
    },
  ];

  // Helper Functions
  const reformatConvoHistory = (history: ConversationHistory[]): string => {
    return history
      .map(
        (item) =>
          `Previous ${item.role} question: ${item.question}\nPrevious Follow Up Question: ${item.llm_response}`
      )
      .join("\n\n");
  };

  const performSearch = async (searchText: string) => {
    if (!searchText.trim()) return;

    setConversation((prev) => [...prev, { type: "user", content: searchText }]);
    setIsLoading(true);

    const fetchData = async () => {
      await fetchEventSource(
        "http://127.0.0.1:8000/a***REMOVED***llm?prompt=" +
          encodeURIComponent(searchText) +
          "&convoHistory=" +
          encodeURIComponent(reformatConvoHistory(convoHistory)) +
          "&roleFilter=" +
          encodeURIComponent(userRole) +
          "&contentType=" +
          encodeURIComponent(contentType) +
          "&resourceType=" +
          encodeURIComponent(resourceType),
        {
          method: "GET", // Using GET method for RESTful endpoint
          headers: {
            Accept: "text/event-stream", // Telling the server we expect a stream
          },
          onopen: async (res) => {
            if (res.ok && res.status === 200) {
              console.log("Connection made ", res);
            } else if (
              res.status >= 400 &&
              res.status < 500 &&
              res.status !== 429
            ) {
              console.log("Client-side error ", res);
            }
          },
          onmessage(event) {
            const parsedData = JSON.parse(event.data);
            console.log(parsedData);
            // setData((data) => [...data, parsedData]); // Important to set the data this way, otherwise old data may be overwritten if the stream is too fast
          },
          onclose() {
            console.log("Connection closed by the server");
          },
          onerror(err) {
            console.log("There was an error from server", err);
          },
        }
      );
    };
    fetchData();
    try {
      // Make API request
      throw new Error("Error: Fetching data failed");
      const response = await fetch("http://127.0.0.1:8000/graphql", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
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
            resourceType: resourceType,
          },
        }),
      });

      const data = await response.json();
      const results = data.data.askLlm;

      // Handle response based on type
      if (results[0]?.title === "follow-up") {
        // Handle chat responses
        setConvoHistory((prev) => [
          ...prev,
          {
            role: "user",
            question: searchText,
            llm_response: results[0].summary,
          },
        ]);
        setConversation((prev) => [
          ...prev,
          { type: "assistant", content: results[0].summary },
        ]);
      } else {
        // Handle document responses
        setConversation((prev) => [
          ...prev,
          { type: "assistant", content: "Here's what I found:", results },
        ]);
      }
    } catch (error) {
      console.error(error);
      setConversation((prev) => [
        ...prev,
        {
          type: "assistant",
          content: "Sorry, I encountered an error while searching.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const toSearch = inputValue;
    setInputValue("");
    await performSearch(toSearch);
  };

  const handleSuggestionClick = async (
    suggestion: string,
    index: number,
    type: string
  ) => {
    if (type == "document") {
      setConversation((prev) => [
        ...prev,
        { type: "user", content: suggestion },
      ]);
      setTimeout(() => {
        setConversation((prev) => [
          ...prev,
          {
            type: "assistant",
            content: "Here's what I found:",
            results: [
              {
                title: popularDocumentsByRole[userRole][index].title,
                link:
                  "http://localhost:5173" +
                  popularDocumentsByRole[userRole][index].link,
                summary: popularDocumentsByRole[userRole][index].summary,
                citations: [],
              },
            ],
          },
        ]);
      }, 100);
    } else {
      await performSearch(suggestion);
    }
  };

  // UI Components
  const RoleSelection = () => (
    <div className="flex flex-col items-center justify-center p-4">
      <h1 className="text-4xl font-bold mb-6 text-blue-700">
        Choose Your Role
      </h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-7xl">
        {userRoles.map((role) => (
          <button
            key={role.id}
            onClick={() => {
              setUserRole(role.id);
              setConversation([
                {
                  type: "assistant",
                  content: `Welcome to the New England First Amendment Coalition, the region's leading defender of First Amendment freedoms and government transparency. ${
                    role.id &&
                    `I see that you are a${
                      ["a", "e", "i", "o", "u"].includes(role.id[0]) ? "n" : ""
                    } ${role.id}.`
                  } How can I help you?`,
                },
              ]);
            }}
            className="p-6 bg-blue-50 shadow-md rounded-lg transition-transform hover:scale-105"
          >
            <h2 className="text-2xl font-semibold text-gray-800">
              {role.title}
            </h2>
            <p className="mt-2 text-sm text-gray-600">{role.description}</p>
          </button>
        ))}
      </div>
    </div>
  );

  const SuggestionButton = ({
    suggestion,
    index,
    type,
  }: {
    suggestion: string;
    index: number;
    type: string;
  }) => {
    return (
      <button
        onClick={() => handleSuggestionClick(suggestion, index, type)}
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

  const MessageBubble = ({ msg, index }: { msg: Message; index: number }) => {
    const isUser = msg.type === "user";
    const isLatestMessage = index === conversation.length - 1;
    const shouldAnimate =
      isLatestMessage && conversation.length > prevLength.current;

    useEffect(() => {
      prevLength.current = conversation.length;
    }, [conversation.length]);

    return (
      <div className={`flex ${isUser ? "justify-end" : "justify-start"} my-2`}>
        <div
          className={`
            max-w-[80%] rounded-2xl p-4
            ${
              isUser
                ? "bg-blue-500 text-white mr-2 rounded-br-sm"
                : "bg-gray-50 shadow-sm border border-gray-100 ml-2 rounded-bl-sm"
            }
            transition-all duration-200
            hover:shadow-md
            ${shouldAnimate && "animate-once-messageIn"}
          `}
        >
          <p
            className={`
            text-base leading-relaxed
            ${isUser ? "text-white" : "text-gray-800"}
          `}
          >
            {msg.content}
          </p>

          {msg.results && (
            <div className={`mt-4 space-y-4 `}>
              {msg.results.map((result, index) => (
                <div key={index}>
                  <SearchResultItem
                    result={result}
                    isUserMessage={false}
                    shouldAnimate={shouldAnimate}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  };

  const SearchResultItem = ({
    result,
    isUserMessage,
    shouldAnimate,
  }: {
    result: SearchResult;
    isUserMessage: boolean;
    shouldAnimate: boolean;
  }) => (
    <div
      className={`border-t border-gray-200 pt-4 ${
        shouldAnimate && "animate-once-messageIn"
      }`}
    >
      <h3 className="font-medium">
        <a
          href={result.link}
          className={`${
            isUserMessage ? "text-blue-200" : "text-blue-600"
          } hover:underline`}
          target="_blank"
          rel="noopener noreferrer"
        >
          {result.title}
        </a>
      </h3>
      <p className={`mt-2 ${isUserMessage ? "text-white" : "text-gray-700"}`}>
        {result.summary}
        {result.citations.map((citation, index) => (
          <span key={index} className="inline-block mx-1 group relative">
            <span className={"text-blue-500"}>
              {" "}
              {/*isUserMessage ? 'text-blue-200' */}[{citation.id}]
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
              className="bg-blue-500 text-white border-2 border-blue-500 px-4 py-2 rounded-md shadow-lg 
                transition-all duration-200 ease-in-out
                hover:bg-blue-600 hover:border-blue-600 hover:shadow-xl 
                active:bg-blue-700 active:scale-95
                focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              Edit Role
            </button>
            {contentAndResourceTypes.map((select, index) => (
              <select
                title={
                  index === 0 ? "Select Resource Type" : "Select Content Type"
                }
                key={index}
                className="bg-white text-blue-500 border-2 border-blue-500 px-4 py-2 rounded-full shadow-lg
                  transition-all duration-200 ease-in-out
                  hover:border-blue-600 hover:text-blue-600 hover:shadow-xl
                  focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                  cursor-pointer"
                onChange={(e) =>
                  index === 0
                    ? setResourceType(e.target.value)
                    : setContentType(e.target.value)
                }
              >
                {select.options.map((option, index) => (
                  <option
                    key={index}
                    value={option.value}
                    className="text-gray-800 bg-white hover:bg-blue-50"
                  >
                    {option.label}
                  </option>
                ))}
              </select>
            ))}
          </div>

          {/* Conversation Container */}
          <div
            className="flex-1 overflow-y-auto p-4"
            style={{ marginBottom: "80px" }}
          >
            <div className="max-w-4xl mx-auto space-y-4">
              {conversation.map((msg, index) => (
                <MessageBubble key={index} msg={msg} index={index} />
              ))}

              {/* Initial suggestions */}
              {conversation.length === 1 && (
                <div className="fixed bottom-24 left-1/2 -translate-x-1/2 w-full max-w-3xl px-4 py-6 flex flex-col items-center gap-4 z-10">
                  {/* Popular Documents */}
                  <div className="text-center">
                    <h3 className="text-lg font-semibold mb-2 text-black">
                      Popular Documents for{" "}
                      {userRole.charAt(0).toUpperCase() + userRole.slice(1)}s:
                    </h3>
                    <div className="flex flex-wrap justify-center gap-4">
                      {suggestionsByRole[userRole]?.map(
                        (suggestion, index: number) => (
                          <>
                            <SuggestionButton
                              key={index}
                              suggestion={suggestion}
                              index={index}
                              type={index < 2 ? "document" : "discussion"}
                            />
                            {index === 1 && (
                              <div className="w-full mt-2">
                                <h3 className="text-lg font-semibold text-black">
                                  Common Questions:
                                </h3>
                              </div>
                            )}
                          </>
                        )
                      )}
                    </div>
                  </div>
                </div>
              )}
              <div ref={conversationEndRef} />
            </div>
          </div>

          {/* Search Input */}
          <div className="p-4 border-t bg-white fixed bottom-0 w-full z-20 shadow-lg">
            <form
              onSubmit={handleSearch}
              className="max-w-4xl mx-auto flex gap-2"
            >
              <input
                type="text"
                value={inputValue}
                onChange={handleInputChange}
                placeholder="Ask a question..."
                className="flex-1 p-2 border rounded-lg
                  transition-all duration-200 ease-in-out
                  focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 focus:outline-none
                  hover:border-blue-300 hover:shadow-sm
                  disabled:opacity-50 disabled:cursor-not-allowed
                  placeholder:text-gray-400"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={isLoading}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg 
                  transition-all duration-200 ease-in-out
                  hover:bg-blue-600 hover:shadow-md
                  active:scale-95
                  focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                  disabled:opacity-50 disabled:cursor-not-allowed
                  disabled:hover:bg-blue-500 disabled:hover:shadow-none disabled:active:scale-100"
              >
                {isLoading ? (
                  <div className="w-6 h-6 border-t-2 border-white rounded-full animate-spin" />
                ) : (
                  <Send className="w-6 h-6 transition-transform group-hover:scale-105" />
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
