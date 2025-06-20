import React, { useState, useEffect } from 'react';
import { BASE_URL } from '../constant/backend';

interface LoadingStatus {
  current: number;
  total: number;
  status: string;
  is_loading: boolean;
}

const LoadingStatus: React.FC = () => {
  const [loadingStatus, setLoadingStatus] = useState<LoadingStatus | null>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const fetchLoadingStatus = async () => {
      try {
        const response = await fetch(`${BASE_URL}/loading-status`);
        if (response.ok) {
          const status: LoadingStatus = await response.json();
          setLoadingStatus(status);

          // Show the status bar if documents are being loaded
          setIsVisible(status.is_loading || status.status === 'adding_documents');
        }
      } catch (error) {
        console.error('Error fetching loading status:', error);
      }
    };

    // Initial fetch
    fetchLoadingStatus();

    // Poll every 2 seconds while loading
    const interval = setInterval(() => {
      if (loadingStatus?.is_loading || loadingStatus?.status === 'adding_documents') {
        fetchLoadingStatus();
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [loadingStatus?.is_loading, loadingStatus?.status]);

  if (!isVisible || !loadingStatus) {
    return null;
  }

  const getStatusMessage = () => {
    switch (loadingStatus.status) {
      case 'initializing':
        return 'Initializing vector store...';
      case 'adding_documents':
        return `Adding documents to knowledge base: ${loadingStatus.current}/${loadingStatus.total}`;
      case 'complete':
        return 'Knowledge base ready!';
      case 'error':
        return 'Error loading documents';
      default:
        return 'Loading...';
    }
  };

  const getProgressPercentage = () => {
    if (loadingStatus.total === 0) return 0;
    return Math.round((loadingStatus.current / loadingStatus.total) * 100);
  };

  return (
    <div className="fixed top-0 left-0 right-0 bg-blue-50 border-b border-blue-200 p-3 z-50">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-4 h-4">
              {loadingStatus.is_loading ? (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
              ) : (
                <div className="w-4 h-4 bg-green-500 rounded-full"></div>
              )}
            </div>
            <span className="text-sm font-medium text-blue-900">{getStatusMessage()}</span>
          </div>

          {loadingStatus.status === 'adding_documents' && (
            <div className="flex items-center space-x-2">
              <span className="text-xs text-blue-700">{getProgressPercentage()}%</span>
              <div className="w-32 bg-blue-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${getProgressPercentage()}%` }}
                ></div>
              </div>
            </div>
          )}

          {loadingStatus.status === 'complete' && (
            <button
              onClick={() => setIsVisible(false)}
              className="text-xs text-blue-700 hover:text-blue-900"
            >
              Dismiss
            </button>
          )}
        </div>

        {loadingStatus.status === 'adding_documents' && (
          <div className="mt-2 text-xs text-blue-600">
            The chatbot is available while documents are being added to the knowledge base.
          </div>
        )}
      </div>
    </div>
  );
};

export default LoadingStatus;
