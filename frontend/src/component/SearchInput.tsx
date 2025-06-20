import { Send } from 'lucide-react';
import { FormEvent } from 'react';

interface SearchInputProps {
  handleSearch: (e: React.FormEvent<HTMLFormElement>) => Promise<void>;
  handleInputChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  inputValue: string;
  isLoading: boolean;
}

export const SearchInput: React.FC<SearchInputProps> = ({
  handleSearch,
  handleInputChange,
  inputValue,
  isLoading,
}) => {
  return (
    <div className="p-4 border-t bg-white fixed bottom-0 w-full z-20 shadow-lg">
      <form onSubmit={handleSearch} className="max-w-4xl mx-auto flex gap-2">
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
  );
};
