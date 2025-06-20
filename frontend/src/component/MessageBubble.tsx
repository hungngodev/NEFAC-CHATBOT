import { Message } from '../pages/SearchBar';
import { useEffect, useState } from 'react';
import { SearchResultItem } from './SearchResultItem';
import { SourceLinks } from './SourceLinks';
import remarkGfm from 'remark-gfm';
import ReactMarkdown from 'react-markdown';
interface MessageBubbleProps {
  msg: Message;
  index: number;
  conversation: Message[];
  prevLength: React.MutableRefObject<number>;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({
  msg,
  index,
  conversation,
  prevLength,
}) => {
  const isUser = msg.type === 'user';
  const isLatestMessage = index === conversation.length - 1;
  const shouldAnimate = isLatestMessage && conversation.length > prevLength.current;
  const [showDetailedSources, setShowDetailedSources] = useState(false);

  useEffect(() => {
    prevLength.current = conversation.length;
  }, [conversation.length]);

  // User messages remain unchanged
  if (isUser) {
    return (
      <div className="flex justify-end my-2">
        <div
          className={`
            max-w-[80%] rounded-2xl p-4
            bg-blue-500 text-white mr-2 rounded-br-sm
            transition-all duration-200
            hover:shadow-md
            ${shouldAnimate && 'animate-once-messageIn'}
          `}
        >
          <div className="text-base leading-relaxed text-white">
            <ReactMarkdown children={msg.content} remarkPlugins={[remarkGfm]} />
          </div>
        </div>
      </div>
    );
  }

  // Assistant messages with new layout: sources at top, response below
  return (
    <div className="flex justify-start my-2">
      <div
        className={`
          max-w-[90%] sm:max-w-[85%] ml-2
          transition-all duration-200
          ${shouldAnimate && 'animate-once-messageIn'}
        `}
      >
        {/* Source Links Section - Only show if there are results */}
        {msg.results && msg.results.length > 0 && <SourceLinks results={msg.results} />}

        {/* LLM Response Section */}
        <div
          className={`
            rounded-2xl p-4 rounded-bl-sm
            bg-gray-50 shadow-sm border border-gray-100
            transition-all duration-200
            hover:shadow-md
          `}
        >
          <div className="text-base leading-relaxed text-gray-800">
            <ReactMarkdown children={msg.content} remarkPlugins={[remarkGfm]} />
          </div>

          {/* Toggle for detailed sources */}
          {msg.results && msg.results.length > 0 && (
            <div className="mt-4 pt-3 border-t border-gray-200">
              <button
                onClick={() => setShowDetailedSources(!showDetailedSources)}
                className="flex items-center text-sm text-blue-600 hover:text-blue-800 font-medium"
              >
                <svg
                  className={`w-4 h-4 mr-1 transition-transform ${
                    showDetailedSources ? 'rotate-180' : ''
                  }`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
                {showDetailedSources ? 'Hide' : 'Show'} detailed source information
              </button>
            </div>
          )}

          {/* Detailed Sources Section - Collapsible */}
          {showDetailedSources && msg.results && msg.results.length > 0 && (
            <div className="mt-4 space-y-4 border-t border-gray-200 pt-4">
              {msg.results.map((result, index) => (
                <SearchResultItem key={index} result={result} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
