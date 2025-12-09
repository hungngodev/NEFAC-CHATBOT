import { getApiKey } from "@/lib/api-key";
import { type Message } from "@langchain/langgraph-sdk";
import { useStream } from "@langchain/langgraph-sdk/react";
import {
  type RemoveUIMessage,
  type UIMessage,
} from "@langchain/langgraph-sdk/react-ui";
import { useQueryState } from "nuqs";
import React, {
  createContext,
  ReactNode,
  useContext,
  useEffect,
  useState,
  useMemo,
} from "react";
import { toast } from "sonner";
import { useThreads } from "./Thread";
import { createClient } from "./client";
import { DEFAULT_API_URL, DEFAULT_ASSISTANT_ID } from "@/constants";
import { handleCustomEvent, resetRunStartTime, setRunStartTime } from "@/lib/events";
export type StateType = {
  messages: Message[];
  ui?: UIMessage[];
  isFinalResponseStreaming?: boolean;
  // Deep research status (both real-time and persisted)
  deep_research_status?: {
    status: string;
    progress: number;
    total_steps: number;
    estimated_time_remaining: number;
  };
};

const useTypedStream = useStream<
  StateType,
  {
    UpdateType: {
      messages?: Message[] | Message | string;
      ui?: (UIMessage | RemoveUIMessage)[] | UIMessage | RemoveUIMessage;
      context?: Record<string, unknown>;
    };
    CustomEventType: UIMessage | RemoveUIMessage | { name: string; data?: any };
  }
>;

type StreamContextType = ReturnType<typeof useTypedStream> & {
  hasActiveRun: boolean;
};
const StreamContext = createContext<StreamContextType | undefined>(undefined);

async function sleep(ms = 4000) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function checkGraphStatus(
  apiUrl: string,
  apiKey: string | null,
): Promise<boolean> {
  try {
    const res = await fetch(`${apiUrl}/info`, {
      ...(apiKey && {
        headers: {
          "X-Api-Key": apiKey,
        },
      }),
    });

    return res.ok;
  } catch (e) {
    console.error(e);
    return false;
  }
}

const StreamSession = ({
  children,
  apiKey,
  apiUrl,
  assistantId,
}: {
  children: ReactNode;
  apiKey: string | null;
  apiUrl: string;
  assistantId: string;
}) => {
  const [threadId, setThreadId] = useQueryState("threadId");
  const [hasActiveRun, setHasActiveRun] = useState(false);
  const [isCheckingRuns, setIsCheckingRuns] = useState(true);
  const [reconnectedStatus, setReconnectedStatus] = useState<StateType["deep_research_status"] | null>(null);
  const { getThreads, setThreads } = useThreads();
  const streamValue = useTypedStream({
    apiUrl,
    apiKey: apiKey ?? undefined,
    assistantId,
    threadId: threadId ?? null,
    fetchStateHistory: true,
    reconnectOnMount: () => window.localStorage,
    onCustomEvent: (event, options) => {
      handleCustomEvent(event, options);
    },
    onThreadId: (id) => {
      setThreadId(id);
      // Refetch threads list when thread ID changes.
      // Wait for some seconds before fetching so we're able to get the new thread that was created.
      sleep().then(() => getThreads().then(setThreads).catch(console.error));
    },
  });

  useEffect(() => {
    if (!threadId || !apiUrl) {
      setHasActiveRun(false);
      setIsCheckingRuns(false);
      return;
    }

    if (streamValue.isLoading) {
      setIsCheckingRuns(false);
      return;
    }

    setIsCheckingRuns(true);
    let cancelled = false;
    
    const debounceTimeout = setTimeout(async () => {
      try {
        const client = createClient(apiUrl, apiKey ?? undefined);
        const [pendingRuns, runningRuns] = await Promise.all([
          client.runs.list(threadId, { status: "pending", limit: 1 }),
          client.runs.list(threadId, { status: "running", limit: 1 }),
        ]);
        if (!cancelled) {
          setHasActiveRun(pendingRuns.length > 0 || runningRuns.length > 0);
        }
      } catch (e) {
        console.error("Failed to check active runs:", e);
        if (!cancelled) {
          setHasActiveRun(false);
        }
      } finally {
        if (!cancelled) {
          setIsCheckingRuns(false);
        }
      }
    }, 100);

    return () => {
      cancelled = true;
      clearTimeout(debounceTimeout);
    };
  }, [threadId, apiUrl, apiKey, streamValue.isLoading]);

  useEffect(() => {
    if (streamValue.isLoading) {
      setHasActiveRun(false);
      setIsCheckingRuns(false);
      setReconnectedStatus(null); // Clear stale reconnection data when new stream starts
      resetRunStartTime(); // Reset time-based progress for new run
    }
  }, [streamValue.isLoading]);

  useEffect(() => {
    if (!hasActiveRun || streamValue.isLoading || !threadId || !apiUrl) {
      return;
    }

    let cancelled = false;
    const abortController = new AbortController();
    const EXPECTED_DURATION_SECONDS = 710;

    const deriveStatusFromEvent = (eventName: string): string | null => {
      if (eventName.includes("final_report")) return "Generating final report...";
      if (eventName.includes("retrieve_subgraph")) return "Retrieving documents...";
      if (eventName.includes("multi_query")) return "Executing search queries...";
      if (eventName.includes("query_transformer")) return "Transforming queries...";
      if (eventName.includes("researcher")) return "Analyzing research data...";
      if (eventName.includes("research_team")) return "Research team working...";
      if (eventName.includes("research_supervisor") && !eventName.includes("research_team")) return "Coordinating research...";
      if (eventName.includes("write_research_brief")) return "Formulating research strategy...";
      return null;
    };

    const joinActiveRun = async () => {
      try {
        const client = createClient(apiUrl, apiKey ?? undefined);
        const [runningRuns, pendingRuns] = await Promise.all([
          client.runs.list(threadId, { status: "running", limit: 1 }),
          client.runs.list(threadId, { status: "pending", limit: 1 }),
        ]);
        const activeRun = runningRuns[0] || pendingRuns[0];
        if (!activeRun || cancelled) return;

        // Set run start time for time-based progress calculation
        const activeRunStartTime = new Date(activeRun.created_at).getTime();
        setRunStartTime(activeRunStartTime);

        for await (const chunk of client.runs.joinStream(threadId, activeRun.run_id, {
          signal: abortController.signal,
        })) {
          if (cancelled) break;

          let statusText: string | null = null;

          // Handle custom events from backend
          if (chunk.event === "custom" && chunk.data?.name === "deep_research_update" && chunk.data?.data) {
            statusText = chunk.data.data.status;
          } else {
            // Derive status from chunk event name (fallback)
            statusText = deriveStatusFromEvent(chunk.event);
          }
          
          if (statusText) {
            // Calculate time-based progress using the stored run start time
            const elapsedSeconds = (Date.now() - activeRunStartTime) / 1000;
            const progress = Math.min(95, Math.floor((elapsedSeconds / EXPECTED_DURATION_SECONDS) * 100));
            const remainingSeconds = Math.max(0, EXPECTED_DURATION_SECONDS - elapsedSeconds);
            
            setReconnectedStatus({
              status: statusText,
              progress: Math.max(1, progress),
              total_steps: 100,
              estimated_time_remaining: Math.floor(remainingSeconds),
            });
          }

          if (chunk.event === "end") {
            setHasActiveRun(false);
          }
        }
      } catch (e) {
        if (!cancelled && (e as Error).name !== "AbortError") {
          console.error("[Stream] Failed to join stream:", e);
        }
      }
    };

    joinActiveRun();

    return () => {
      cancelled = true;
      abortController.abort();
    };
  }, [hasActiveRun, streamValue.isLoading, threadId, apiUrl, apiKey]);

  useEffect(() => {
    checkGraphStatus(apiUrl, apiKey).then((ok) => {
      if (!ok) {
        toast.error("Failed to connect to LangGraph server", {
          description: () => (
            <p>
              Please ensure your graph is running at <code>{apiUrl}</code> and
              your API key is correctly set (if connecting to a deployed graph).
            </p>
          ),
          duration: 10000,
          richColors: true,
          closeButton: true,
        });
      }
    });
  }, [apiKey, apiUrl]);

  // Compute on every render to ensure updates from mutate() are reflected
  // Wrapped in useMemo to prevent unnecessary re-renders of child components
  const extendedStreamValue = useMemo(() => {
    const baseValues = streamValue.values || {};
    const streamStatus = (baseValues as Record<string, unknown>).deep_research_status as StateType["deep_research_status"] | undefined;
    
    // Priority: reconnectedStatus (live joinStream) > streamStatus (may be stale checkpoint)
    const effectiveStatus = reconnectedStatus || streamStatus;
    
    return {
      ...streamValue,
      values: {
        ...baseValues,
        ...(effectiveStatus && { deep_research_status: effectiveStatus }),
      },
      hasActiveRun: hasActiveRun || isCheckingRuns,
    };
  }, [streamValue, streamValue.values, reconnectedStatus, hasActiveRun, isCheckingRuns]);

  return (
    <StreamContext.Provider value={extendedStreamValue}>
      {children}
    </StreamContext.Provider>
  );
};



export const StreamProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  // Use URL params with env var fallbacks
  const [apiUrl, setApiUrl] = useQueryState("apiUrl", {
    defaultValue: DEFAULT_API_URL,
    clearOnDefault: false,
  });
  const [assistantId, setAssistantId] = useQueryState("assistantId", {
    defaultValue: DEFAULT_ASSISTANT_ID,
    clearOnDefault: false,
  });

  // For API key, use localStorage with env var fallback
  const [apiKey, _setApiKey] = useState(() => {
    const storedKey = getApiKey();
    return storedKey || "";
  });

  const setApiKey = (key: string) => {
    window.localStorage.setItem("lg:chat:apiKey", key);
    _setApiKey(key);
  }

  useEffect(() => {

    let resolvedUrl = DEFAULT_API_URL;
    if (resolvedUrl.startsWith("/") && typeof window !== "undefined") {
      resolvedUrl = `${window.location.origin}${resolvedUrl}`;
    }
    setApiUrl(resolvedUrl);
    setAssistantId(DEFAULT_ASSISTANT_ID);
    setApiKey("");
  }, []);


  return (
    <StreamSession
      apiKey={apiKey}
      apiUrl={apiUrl}
      assistantId={assistantId}
    >
      {children}
    </StreamSession>
  );
};

// Create a custom hook to use the context
export const useStreamContext = (): StreamContextType => {
  const context = useContext(StreamContext);
  if (context === undefined) {
    throw new Error("useStreamContext must be used within a StreamProvider");
  }
  return context;
};

export default StreamContext;
