// Use environment variable for BASE_URL, fallback to localhost for development
const getBaseUrl = () => {
  // Check if we're running in a container (Docker)
  if (typeof window !== 'undefined' && window.location.hostname !== 'localhost') {
    return '/api'; // Use relative path when in container
  }
  // Use environment variable if set, otherwise fallback to localhost
  return import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
};

export const BASE_URL = getBaseUrl();
export const FRONTEND_URL = 'http://localhost';
