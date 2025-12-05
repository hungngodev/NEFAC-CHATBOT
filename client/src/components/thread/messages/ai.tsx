import React, { Fragment, useEffect, useState } from "react";

import { MessageContentComplex } from "@langchain/core/messages";
import { parsePartialJson } from "@langchain/core/output_parsers";
import { AIMessage, Checkpoint, Message } from "@langchain/langgraph-sdk";
import { LoadExternalComponent } from "@langchain/langgraph-sdk/react-ui";
import { parseAsBoolean, useQueryState } from "nuqs";

import { isAgentInboxInterruptSchema } from "@/lib/agent-inbox-interrupt";
import { getApiKey } from "@/lib/api-key";
import { cn } from "@/lib/utils";
import { StateType, useStreamContext } from "@/providers/Stream";
import { DEFAULT_API_URL } from "@/constants";

import { ThreadView } from "../agent-inbox";
import { useArtifact } from "../artifact";
import { MarkdownText } from "../markdown-text";
import { getContentString } from "../utils";
import { DocumentList } from "./document-list";
import { GenericInterruptView } from "./generic-interrupt";
import { BranchSwitcher, CommandBar } from "./shared";
import { ToolCalls, ToolResult } from "./tool-calls";

function CustomComponent({
  message,
  thread,
}: {
  message: Message;
  thread: ReturnType<typeof useStreamContext>;
}) {
  const artifact = useArtifact();
  const { values } = useStreamContext();
  const customComponents = values.ui?.filter(
    (ui) => ui.metadata?.message_id === message.id,
  );

  if (!customComponents?.length) return null;
  return (
    <Fragment key={message.id}>
      {customComponents.map((customComponent) => (
        <LoadExternalComponent
          key={customComponent.id}
          stream={thread}
          message={customComponent}
          meta={{ ui: customComponent, artifact }}
        />
      ))}
    </Fragment>
  );
}

function parseAnthropicStreamedToolCalls(
  content: MessageContentComplex[],
): AIMessage["tool_calls"] {
  const toolCallContents = content.filter((c) => c.type === "tool_use" && c.id);

  return toolCallContents.map((tc) => {
    const toolCall = tc as Record<string, any>;
    let json: Record<string, any> = {};
    if (toolCall?.input) {
      try {
        json = parsePartialJson(toolCall.input) ?? {};
      } catch {
        // Pass
      }
    }
    return {
      name: toolCall.name ?? "",
      id: toolCall.id ?? "",
      args: json,
      type: "tool_call",
    };
  });
}

interface InterruptProps {
  interrupt?: unknown;
  isLastMessage: boolean;
  hasNoAIOrToolMessages: boolean;
}

function Interrupt({
  interrupt,
  isLastMessage,
  hasNoAIOrToolMessages,
}: InterruptProps) {
  const fallbackValue = Array.isArray(interrupt)
    ? (interrupt as Record<string, any>[])
    : (((interrupt as { value?: unknown } | undefined)?.value ??
        interrupt) as Record<string, any>);

  // Hide generic "breakpoint" interrupts that don't have payload
  // This fixes the issue where "when: breakpoint" appears unexpectedly
  if (
    !Array.isArray(interrupt) &&
    interrupt &&
    typeof interrupt === "object" &&
    Object.keys(interrupt).length === 1 &&
    (interrupt as any).when === "breakpoint"
  ) {
    return null;
  }

  return (
    <>
      {isAgentInboxInterruptSchema(interrupt) &&
        (isLastMessage || hasNoAIOrToolMessages) && (
          <ThreadView interrupt={interrupt} />
        )}
      {interrupt &&
      !isAgentInboxInterruptSchema(interrupt) &&
      (isLastMessage || hasNoAIOrToolMessages) ? (
        <GenericInterruptView interrupt={fallbackValue} />
      ) : null}
    </>
  );
}

export const AssistantMessage = React.memo(function AssistantMessage({
  message,
  isLoading,
  handleRegenerate,
  forceShowToolCalls,
  thread,
  isLastMessage,
  hasNoAIOrToolMessages,
  meta,
  interrupt,
}: {
  message: Message | undefined;
  isLoading: boolean;
  handleRegenerate: (parentCheckpoint: Checkpoint | null | undefined) => void;
  forceShowToolCalls?: boolean;
  thread: ReturnType<typeof useStreamContext>;
  isLastMessage: boolean;
  hasNoAIOrToolMessages: boolean;
  meta: any;
  interrupt: any;
}) {
  const content = message?.content ?? [];
  const contentString = getContentString(content);
  const [hideToolCallsQuery] = useQueryState(
    "hideToolCalls",
    parseAsBoolean.withDefault(false),
  );
  const hideToolCalls = forceShowToolCalls ? false : hideToolCallsQuery;

  const parentCheckpoint = meta?.firstSeenState?.parent_checkpoint;
  const anthropicStreamedToolCalls = Array.isArray(content)
    ? parseAnthropicStreamedToolCalls(content)
    : undefined;

  const hasToolCalls =
    message &&
    "tool_calls" in message &&
    message.tool_calls &&
    message.tool_calls.length > 0;
  const toolCallsHaveContents =
    hasToolCalls &&
    message.tool_calls?.some(
      (tc) => tc.args && Object.keys(tc.args).length > 0,
    );
  const hasAnthropicToolCalls = !!anthropicStreamedToolCalls?.length;
  const isToolResult = message?.type === "tool";

  if (isToolResult && hideToolCalls) {
    return null;
  }

  return (
    <div className="group mr-auto flex w-full items-start gap-2">
      <div className="flex w-full flex-col gap-2">
        {isToolResult ? (
          <>
            <ToolResult message={message} />
            <Interrupt
              interrupt={interrupt}
              isLastMessage={isLastMessage}
              hasNoAIOrToolMessages={hasNoAIOrToolMessages}
            />
          </>
        ) : (
          <>
            {contentString.length > 0 ? (
              <div className="py-1">
                <MarkdownText>{contentString}</MarkdownText>
              </div>
            ) : (
              !hasToolCalls &&
              !hasAnthropicToolCalls &&
              !isToolResult && (
                <div className="py-1 text-xs text-gray-400 italic">
                  (Empty message content)
                </div>
              )
            )}

            {!hideToolCalls && (
              <>
                {(hasToolCalls && toolCallsHaveContents && (
                  <ToolCalls toolCalls={message.tool_calls} />
                )) ||
                  (hasAnthropicToolCalls && (
                    <ToolCalls toolCalls={anthropicStreamedToolCalls} />
                  )) ||
                  (hasToolCalls && (
                    <ToolCalls toolCalls={message.tool_calls} />
                  ))}
              </>
            )}

            {message && (
              <CustomComponent
                message={message}
                thread={thread}
              />
            )}
            <Interrupt
              interrupt={interrupt}
              isLastMessage={isLastMessage}
              hasNoAIOrToolMessages={hasNoAIOrToolMessages}
            />
            <div
              className={cn(
                "mr-auto flex items-center gap-2 transition-opacity",
                "opacity-0 group-focus-within:opacity-100 group-hover:opacity-100",
              )}
            >
              <BranchSwitcher
                branch={meta?.branch}
                branchOptions={meta?.branchOptions}
                onSelect={(branch) => thread.setBranch(branch)}
                isLoading={isLoading}
              />
              <CommandBar
                content={contentString}
                isLoading={isLoading}
                isAiMessage={true}
                handleRegenerate={() => handleRegenerate(parentCheckpoint)}
              />
            </div>

            {message?.additional_kwargs?.final_documents && (
              <DocumentList
                documents={message.additional_kwargs.final_documents as any[]}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}, (prev, next) => {
  // Custom comparison to avoid re-renders when `thread` context changes but message is stable
  const prevContent = getContentString(prev.message?.content ?? []);
  const nextContent = getContentString(next.message?.content ?? []);
  
  return (
    prev.message?.id === next.message?.id &&
    prevContent === nextContent &&
    prev.isLoading === next.isLoading &&
    prev.isLastMessage === next.isLastMessage &&
    prev.hasNoAIOrToolMessages === next.hasNoAIOrToolMessages &&
    // We intentionally ignore `thread` prop changes to prevent re-renders on every token
    // This assumes `thread` methods (setBranch) are stable or we don't care if they are stale for old messages
    JSON.stringify(prev.meta) === JSON.stringify(next.meta) &&
    JSON.stringify(prev.interrupt) === JSON.stringify(next.interrupt)
  );
});

export function AssistantMessageLoading() {
  return (
    <div className="mr-auto flex items-start gap-2">
      <div className="bg-muted flex h-8 items-center gap-1 rounded-2xl px-4 py-2">
        <div className="bg-foreground/50 h-1.5 w-1.5 animate-[pulse_1.5s_ease-in-out_infinite] rounded-full"></div>
        <div className="bg-foreground/50 h-1.5 w-1.5 animate-[pulse_1.5s_ease-in-out_0.5s_infinite] rounded-full"></div>
        <div className="bg-foreground/50 h-1.5 w-1.5 animate-[pulse_1.5s_ease-in-out_1s_infinite] rounded-full"></div>
      </div>
    </div>
  );
}

export const DeepResearchLoading = ({
  isComplete,
}: {
  isComplete?: boolean;
}) => {
  const stream = useStreamContext();
  const values = (stream as any).values || {};

  // Use context status
  const status =
    values.deepResearchStatus || values.deep_research_status;

  const [progress, setProgress] = useState(5);
  const [lastStatus, setLastStatus] = useState("");

  // Monotonic progress update based on status changes
  useEffect(() => {
    if (isComplete) {
      setProgress(100);
      return;
    }

    if (!status?.status) return;

    // Prevent backward jumps
    if (status.status === lastStatus) return;
    setLastStatus(status.status);

    let increment = 0;
    const s = status.status.toLowerCase();

    // Heuristic progress increments based on event type
    if (s.includes("refining")) increment = 5;
    else if (s.includes("formulating")) increment = 10;
    else if (s.includes("coordinating")) increment = 5;
    else if (s.includes("analyzing")) increment = 5;
    else if (s.includes("searching")) increment = 2;
    else if (s.includes("reading")) increment = 2;
    else increment = 1;

    setProgress((prev) => Math.min(95, prev + increment));
  }, [status?.status, isComplete, lastStatus]);

  // Use backend status text if available, otherwise default
  const statusText = status?.status || "Conducting deep research...";

  // Only show complete state if progress is 100 or status indicates completion
  const isActuallyComplete = isComplete && (progress >= 100 || status?.status?.toLowerCase().includes("complete"));

  if (isActuallyComplete) {
    return (
      <div className="bg-muted/30 mr-auto flex w-full flex-col gap-4 rounded-lg border p-4">
        <div className="flex items-center gap-3">
          <div className="relative flex h-3 w-3 items-center justify-center">
             <div className="h-2.5 w-2.5 rounded-full bg-green-500" />
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-medium">Deep Research Complete</span>
            <span className="text-muted-foreground text-xs">
              Research finished. Generating final report...
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-muted/30 mr-auto flex w-full flex-col gap-4 rounded-lg border p-4">
      <div className="flex items-center gap-3">
        <div className="relative flex h-3 w-3">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75"></span>
          <span className="relative inline-flex h-3 w-3 rounded-full bg-blue-500"></span>
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-medium">Deep Research in Progress</span>
          <span className="text-muted-foreground animate-pulse text-xs">
            {statusText}
          </span>
        </div>
      </div>

      <div className="bg-muted h-1.5 w-full overflow-hidden rounded-full">
        <div
          className="h-full bg-gradient-to-r from-blue-600 via-cyan-400 to-blue-600 animate-gradient-x transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        ></div>
      </div>

      <p className="text-muted-foreground mt-1 border-t pt-3 text-xs">
        This process involves searching multiple sources and analyzing complex
        data.
      </p>

    </div>
  );
}
