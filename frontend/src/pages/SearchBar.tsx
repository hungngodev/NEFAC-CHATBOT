import { fetchEventSource } from "@microsoft/fetch-event-source";
import React, { useEffect, useRef, useState } from "react";
import { EditRole } from "../component/EditRole";
import { MessageBubble } from "../component/MessageBubble";
import { RoleSelection } from "../component/RoleSelection";
import { SearchInput } from "../component/SearchInput";
import { SuggestionByRole } from "../component/SuggestionByRole";
import { BASE_URL } from "../constant/backend";
import "./SearchBar.css";

// Types and Interfaces
interface Citation {
  id: string;
  context: string;
}

export interface SearchResult {
  title: string;
  link: string;
  audience: string[];
  nefac_category: string[];
  resource_type: string[];
  chunks: {
    summary: string;
    citations: Citation[];
  }[];
}

export interface Message {
  type: "user" | "assistant";
  content: string;
  results: SearchResult[];
}

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
      results: [],
      content: `Welcome to the New England First Amendment Coalition, the region's leading defender of First Amendment freedoms and government transparency. How can I help you?`,
    },
  ]);
  const prevLength = useRef<number>(1);
  const messageOrderStream = useRef<Set<number>>(new Set());
  const contextOrderStream = useRef<Set<number>>(new Set());
  const contextResultsStream = useRef<SearchResult[]>([]);
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

  const performSearch = async (searchText: string) => {
    if (!searchText.trim()) return;

    // Add initial messages to the conversation
    setConversation((prev) => [
      ...prev,
      { type: "user", content: searchText, results: [] },
      { type: "assistant", content: "Searching...", results: [] },
    ]);
    setIsLoading(true);

    try {
      // Wrap the streaming process in a promise
      await new Promise<void>((resolve, reject) => {
        fetchEventSource(
          BASE_URL +
            "/a***REMOVED***llm?query=" +
            encodeURIComponent(searchText) +
            "&convoHistory=" +
            encodeURIComponent("") +
            "&roleFilter=" +
            encodeURIComponent(userRole) +
            "&contentType=" +
            encodeURIComponent(contentType) +
            "&resourceType=" +
            encodeURIComponent(resourceType),
          {
            method: "GET",
            headers: {
              Accept: "text/event-stream",
            },
            onopen: async (res) => {
              if (res.ok && res.status === 200) {
                console.log("Connection made", res);
              } else if (
                res.status >= 400 &&
                res.status < 500 &&
                res.status !== 429
              ) {
                console.log("Client-side error", res);
              }
            },
            onmessage(event) {
              const parsedData = JSON.parse(event.data);
              console.log(parsedData);
              if (parsedData.context) {
                if (!contextOrderStream.current.has(parsedData.order)) {
                  parsedData.context.forEach((result: any) => {
                    const exist = contextResultsStream.current.findIndex(
                      (r) => r.title === result.title
                    );
                    if (exist !== -1) {
                      contextResultsStream.current[exist].chunks.push({
                        summary: result.summary,
                        citations: [],
                      });
                    } else {
                      contextResultsStream.current.push({
                        title: result.title,
                        link: result.link,
                        audience: result.audience,
                        nefac_category: result.nefac_category,
                        resource_type: result.resource_type,
                        chunks: [
                          {
                            summary: result.summary,
                            citations: [],
                          },
                        ],
                      });
                    }
                  });
                }
                contextOrderStream.current.add(parsedData.order);
              }
              if (parsedData.message) {
                window.history.scrollRestoration = "auto";
                setConversation((prev) => {
                  const last = prev[prev.length - 1];
                  if (messageOrderStream.current.size === 0) {
                    last.content = parsedData.message;
                  } else if (
                    !messageOrderStream.current.has(parsedData.order)
                  ) {
                    last.content += parsedData.message;
                  }
                  messageOrderStream.current.add(parsedData.order);
                  return [...prev];
                });
              }
            },
            onclose() {
              console.log("Connection closed by the server");
              // Clear order sets
              messageOrderStream.current.clear();
              contextOrderStream.current.clear();
              // Update conversation with final results
              setConversation((prev) => {
                window.history.scrollRestoration = "manual";
                const last = prev[prev.length - 1];
                last.results = contextResultsStream.current.map((result) => ({
                  title: result.title,
                  link: result.link,
                  audience: result.audience,
                  nefac_category: result.nefac_category,
                  resource_type: result.resource_type,
                  chunks: result.chunks,
                }));
                // Remove placeholder text
                last.content = last.content.replace("Searching...", "");
                return [...prev];
              });
              // Resolve the promise when the stream is done
              resolve();
            },
            onerror(err) {
              console.log("There was an error from server", err);
              reject(err);
            },
          }
        );
      });
    } catch (error) {
      console.error(error);
      setConversation((prev) => [
        ...prev,
        {
          type: "assistant",
          content: "Sorry, I encountered an error while searching.",
          results: [],
        },
      ]);
    } finally {
      // Clear stream results and stop loading immediately after completion
      contextResultsStream.current = [];
      setIsLoading(false);
    }
  };

  const handleSearch = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const toSearch = inputValue;
    setInputValue("");
    await performSearch(toSearch);
  };

  // Main Render
  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      {userRole === "" ? (
        <RoleSelection
          setUserRole={setUserRole}
          setConversation={setConversation}
        />
      ) : (
        <div>
          {/* Edit Role and Dropdowns */}
          <EditRole
            setUserRole={setUserRole}
            setResourceType={setResourceType}
            setContentType={setContentType}
          />
          <div
            className="flex-1 overflow-y-auto p-4"
            style={{ marginBottom: "80px" }}
          >
            <div className="max-w-4xl mx-auto space-y-4">
              {conversation.map((msg, index) => (
                <MessageBubble
                  key={index}
                  msg={msg}
                  index={index}
                  conversation={conversation}
                  prevLength={prevLength}
                />
              ))}

              {/* Initial suggestions */}
              {conversation.length === 1 && (
                <SuggestionByRole
                  userRole={userRole}
                  setConversation={setConversation}
                  performSearch={performSearch}
                />
              )}
              <div ref={conversationEndRef} />
            </div>
          </div>

          <SearchInput
            handleSearch={handleSearch}
            handleInputChange={handleInputChange}
            inputValue={inputValue}
            isLoading={isLoading}
          />
        </div>
      )}
    </div>
  );
};

export default SearchBar;
