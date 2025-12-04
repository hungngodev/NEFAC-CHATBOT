import { UIMessage, RemoveUIMessage, isUIMessage, isRemoveUIMessage, uiMessageReducer } from "@langchain/langgraph-sdk/react-ui";
import { StateType } from "@/providers/Stream";

// Event Names
export const EVENT_FINAL_RESPONSE_TAG = "final_response_tag";

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
  }
}
