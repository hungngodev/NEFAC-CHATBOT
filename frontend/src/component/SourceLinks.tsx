import React from 'react';

interface SourceLinksProps {
  results: {
    title: string;
    link: string;
    type: string;
    timestamp_seconds?: number;
    summary?: string;
  }[];
}

export const SourceLinks: React.FC<SourceLinksProps> = ({ results }) => {
  if (!results || results.length === 0) {
    return null;
  }

  const getTagInfo = (type: string, link: string) => {
    if (type === 'youtube') {
      return {
        label: 'YouTube',
        className: 'px-1.5 py-0.5 text-xs rounded-full bg-red-400 text-white',
      };
    }

    if (link && link.toLowerCase().includes('youtube')) {
      return {
        label: 'YouTube',
        className: 'px-1.5 py-0.5 text-xs rounded-full bg-red-400 text-white',
      };
    } else if (link && link.toLowerCase().includes('nefac.org')) {
      return {
        label: 'NEFAC Website',
        className: 'px-1.5 py-0.5 text-xs rounded-full bg-blue-500 text-white',
      };
    } else {
      return {
        label: 'NEFAC Website',
        className: 'px-1.5 py-0.5 text-xs rounded-full bg-blue-500 text-white',
      };
    }
  };

  return (
    <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
      <h4 className="text-sm font-semibold text-blue-800 mb-2 flex items-center">
        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
          />
        </svg>
        Sources ({results.length})
      </h4>

      <div className="space-y-2">
        {results.map((result, index) => {
          const tagInfo = getTagInfo(result.type, result.link);

          return (
            <div key={index} className="flex items-start space-x-2">
              <span className="flex-shrink-0 w-6 h-6 bg-blue-600 text-white text-xs font-bold rounded-full flex items-center justify-center">
                {index + 1}
              </span>
              <div className="flex-1 min-w-0">
                <a
                  href={result.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-700 hover:text-blue-900 hover:underline font-medium text-sm block"
                  title={result.title}
                >
                  <div className="line-clamp-2">
                    {result.title}
                    {result.timestamp_seconds && (
                      <span className="text-blue-500 ml-1">
                        (at {Math.floor(result.timestamp_seconds / 60)}:
                        {(result.timestamp_seconds % 60).toString().padStart(2, '0')})
                      </span>
                    )}
                  </div>
                </a>

                <div className="mt-1">
                  <span className={tagInfo.className}>{tagInfo.label}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {results.length > 3 && (
        <div className="mt-2 pt-2 border-t border-blue-200">
          <button className="text-blue-600 hover:text-blue-800 text-xs font-medium">
            View all {results.length} sources
          </button>
        </div>
      )}
    </div>
  );
};
