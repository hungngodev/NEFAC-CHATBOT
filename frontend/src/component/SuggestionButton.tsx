interface SuggestionButtonProps {
  handleSuggestionClick: (
    suggestion: string,
    index: number,
    type: string
  ) => void;
  suggestion: string;
  index: number;
  type: string;
}

export const SuggestionButton: React.FC<SuggestionButtonProps> = ({
  suggestion,
  index,
  type,
  handleSuggestionClick,
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
