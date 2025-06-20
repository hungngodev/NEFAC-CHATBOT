import { useRef, useEffect } from 'react';

// A custom hook to store the previous value of a state or prop
export function usePrevious<T>(value: T): T | undefined {
  const ref = useRef<T>();
  useEffect(() => {
    ref.current = value;
  }, [value]);
  return ref.current;
}
