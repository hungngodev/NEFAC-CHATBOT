import { fetchEventSource } from '@microsoft/fetch-event-source';
import React, { useEffect, useRef, useState } from 'react';
import { MessageBubble } from '../component/MessageBubble';
import { SearchInput } from '../component/SearchInput';
import LoadingStatus from '../component/LoadingStatus';
import { BASE_URL } from '../constant/backend';
import './SearchBar.css';

export interface SearchResult {
  title: string;
  link: string;
  type: string;
  timestamp_seconds?: number;
  summary?: string;
  content?: string;
}

export interface Message {
  type: 'user' | 'assistant';
  content: string;
  results: SearchResult[];
}

const SearchBar = () => {
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversation, setConversation] = useState<Message[]>([
    {
      type: 'assistant',
      results: [],
      content: `Welcome to the New England First Amendment Coalition, the region's leading defender of First Amendment freedoms and government transparency. How can I help you?`,
    },
  ]);
  const prevLength = useRef<number>(1);
  const messageOrderStream = useRef<Set<number>>(new Set());
  const contextOrderStream = useRef<Set<number>>(new Set());

  const contextResultsStream = useRef<SearchResult[]>([]);
  const conversationEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (conversationEndRef.current) {
      conversationEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [conversation]);

  useEffect(() => {
    const last = conversation[conversation.length - 1];
    const hasResults = last?.results?.length;

    if (hasResults) {
      contextResultsStream.current = [];
      setIsLoading(false);
    }
  }, [conversation]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  };

  const performSearch = async (searchText: string) => {
    if (!searchText.trim()) return;

    setConversation((prev) => [
      ...prev,
      { type: 'user', content: searchText, results: [] },
      { type: 'assistant', content: 'Searching...', results: [] },
    ]);
    setIsLoading(true);
    try {
      await fetchEventSource(
        BASE_URL +
          '/ask-llm?query=' +
          encodeURIComponent(searchText) +
          '&convoHistory=' +
          encodeURIComponent(''),
        {
          method: 'GET',
          headers: {
            Accept: 'text/event-stream',
          },
          onopen: async (res) => {
            if (res.ok && res.status === 200) {
              console.log('Connection made ', res);
            } else if (res.status >= 400 && res.status < 500 && res.status !== 429) {
              console.log('Client-side error ', res);
            }
          },
          onmessage(event) {
            const parsedData = JSON.parse(event.data);
            console.log(parsedData);
            if (parsedData.context) {
              if (!contextOrderStream.current.has(parsedData.order)) {
                parsedData.context.forEach((result: SearchResult) => {
                  const exist = contextResultsStream.current.findIndex(
                    (r) =>
                      r.title === result.title && r.timestamp_seconds === result.timestamp_seconds,
                  );
                  if (exist === -1) {
                    contextResultsStream.current.push({
                      title: result.title,
                      link: result.link.replace('/waiting_room', ''),
                      type: result.type || 'unknown',
                      timestamp_seconds: result.timestamp_seconds,
                      summary: result.summary,
                      content: result.content,
                    });
                  }
                });
              }
              contextOrderStream.current.add(parsedData.order);
            }
            if (parsedData.reformulated) {
              // reformulated message received, but not used
            }
            if (parsedData.message) {
              window.history.scrollRestoration = 'auto';
              setConversation((prev) => {
                const last = prev[prev.length - 1];
                if (messageOrderStream.current.size === 0) {
                  last.content = parsedData.message;
                } else if (!messageOrderStream.current.has(parsedData.order)) {
                  last.content += parsedData.message;
                }
                messageOrderStream.current.add(parsedData.order);
                return [...prev];
              });
            }
          },
          onclose() {
            console.log('Connection closed by the server');
            messageOrderStream.current.clear();
            contextOrderStream.current.clear();
            setConversation((prev) => {
              window.history.scrollRestoration = 'manual';
              const last = prev[prev.length - 1];
              last.results = contextResultsStream.current.map((result) => ({
                title: result.title,
                link: result.link.replace('/waiting_room', ''),
                type: result.type,
                timestamp_seconds: result.timestamp_seconds,
                summary: result.summary,
                content: result.content,
              }));
              last.content = last.content.replace('Searching...', '');
              return [...prev];
            });
          },

          onerror(err) {
            console.log('There was an error from server', err);
          },
        },
      );
    } catch (error) {
      console.error(error);
      setConversation((prev) => [
        ...prev,
        {
          type: 'assistant',
          content: 'Sorry, I encountered an error while searching.',
          results: [],
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const toSearch = inputValue;
    setInputValue('');
    await performSearch(toSearch);
  };

  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      <LoadingStatus />
      <div className="flex-1 overflow-y-auto p-4" style={{ marginBottom: '80px' }}>
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
  );
};

export default SearchBar;
