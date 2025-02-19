import { fetchEventSource } from "@microsoft/fetch-event-source";
import React, { useEffect, useRef, useState } from "react";
import { MessageBubble } from "../component/MessageBubble";
import { RoleSelection } from "../component/RoleSelection";
import "./SearchBar.css";
import { SearchInput } from "../component/SearchInput";
import { EditRole } from "../component/EditRole";
import { SuggestionByRole } from "../component/SuggestionByRole";
import { BASE_URL } from "../constant/backend";

// Types and Interfaces
interface Citation {
  id: string;
  context: string;
}

export interface SearchResult {
  title: string;
  link: string;
  summary: string;
  citations: Citation[];
}

export interface Message {
  type: "user" | "assistant";
  content: string;
  results?: SearchResult[];
}

interface ConversationHistory {
  role: string;
  question: string;
  llm_response: string;
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
      content: `Welcome to the New England First Amendment Coalition, the region's leading defender of First Amendment freedoms and government transparency. How can I help you?`,
    },
  ]);
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

  const performSearch = async (searchText: string) => {
    if (!searchText.trim()) return;

    setConversation((prev) => [...prev, { type: "user", content: searchText }]);
    setIsLoading(true);
    try {
      // Make API request
      await fetchEventSource(
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
            if (parsedData.context) {
            }
            if (parsedData.reformulated) {
              // Append reformulated question to reformulatedDiv
            }
            if (parsedData.message) {
              // Append regular data to outputDiv
              setConversation((prev) => []);
            }

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
