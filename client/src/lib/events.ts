import { UIMessage, RemoveUIMessage, isUIMessage, isRemoveUIMessage, uiMessageReducer } from "@langchain/langgraph-sdk/react-ui";
import { StateType } from "@/providers/Stream";

// Event Names
export const EVENT_FINAL_RESPONSE_TAG = "final_response_tag";
export const EVENT_DEEP_RESEARCH_UPDATE = "deep_research_update";

// Run start time tracking for time-based progress
let runStartTime: number | null = null;
const EXPECTED_DURATION_SECONDS = 710;

export function resetRunStartTime() {
  runStartTime = null;
}

export function setRunStartTime(time: number) {
  runStartTime = time;
}

function calculateTimeBasedProgress(): { progress: number; estimated_time_remaining: number } {
  if (!runStartTime) {
    runStartTime = Date.now(); // Initialize on first event if not set
  }
  const elapsedSeconds = (Date.now() - runStartTime) / 1000;
  const progress = Math.min(95, Math.floor((elapsedSeconds / EXPECTED_DURATION_SECONDS) * 100));
  const remainingSeconds = Math.max(0, EXPECTED_DURATION_SECONDS - elapsedSeconds);
  return { progress: Math.max(1, progress), estimated_time_remaining: Math.floor(remainingSeconds) };
}

export type EventMutator = (prev: StateType) => StateType;

export interface StreamOptions {
  mutate: (mutator: EventMutator) => void;
}

export function handleCustomEvent(
  event: UIMessage | RemoveUIMessage | { name: string; data?: any },
  options: StreamOptions
) {
  if (isUIMessage(event) || isRemoveUIMessage(event)) {
    options.mutate((prev) => {
      const ui = uiMessageReducer(prev.ui ?? [], event);
      return { ...prev, ui };
    });
  } else if (event.name === EVENT_FINAL_RESPONSE_TAG) {
    const isFinal = event.data?.is_final ?? true;
    options.mutate((prev) => ({
      ...prev,
      isFinalResponseStreaming: isFinal,
    }));
  } else if (event.name === EVENT_DEEP_RESEARCH_UPDATE) {
    const { progress, estimated_time_remaining } = calculateTimeBasedProgress();
    options.mutate((prev) => ({
      ...prev,
      deep_research_status: {
        ...event.data,
        progress,
        total_steps: 100,
        estimated_time_remaining,
      },
    }));
  }
}
