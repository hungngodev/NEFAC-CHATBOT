import { Message } from "../pages/SearchBar";
import { useEffect } from "react";
import { SearchResultItem } from "./SearchResultItem";
import remarkGfm from "remark-gfm";
import ReactMarkdown from "react-markdown";
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
  const isUser = msg.type === "user";
  const isLatestMessage = index === conversation.length - 1;
  const shouldAnimate =
    isLatestMessage && conversation.length > prevLength.current;

  useEffect(() => {
    prevLength.current = conversation.length;
  }, [conversation.length]);

  // console.log("msg", msg.content);
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
        <div
          className={`
            text-base leading-relaxed
            ${isUser ? "text-white" : "text-gray-800"}
          `}
        >
          <ReactMarkdown children={msg.content} remarkPlugins={[remarkGfm]} />
        </div>

        {msg.results && msg.results.length > 0 && (
        <div className={`mt-4 space-y-4 `}>
          {msg.results.map((result, index) => (
              <SearchResultItem
                key={index}
                result={result}
              />
          ))}
        </div>
      )}
      </div>
    </div>
  );
};
