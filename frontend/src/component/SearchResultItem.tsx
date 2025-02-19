import { SearchResult } from "../pages/SearchBar";

export const SearchResultItem = ({
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
