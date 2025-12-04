import {
  FormEvent,
  ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { AIMessage, Checkpoint, Message } from "@langchain/langgraph-sdk";
import { motion } from "framer-motion";
import {
  ArrowDown,
  LoaderCircle,
  PanelRightClose,
  PanelRightOpen,
  SquarePen,
  XIcon,
} from "lucide-react";
import { parseAsBoolean, useQueryState } from "nuqs";
import { toast } from "sonner";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import { v4 as uuidv4 } from "uuid";

import { useFileUpload } from "@/hooks/use-file-upload";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import {
  DO_NOT_RENDER_ID_PREFIX,
  ensureToolCallsHaveResponses,
} from "@/lib/ensure-tool-responses";
import { cn } from "@/lib/utils";
import { useStreamContext } from "@/providers/Stream";

import { NEFACLogoSVG } from "../icons/langgraph";
import { Button } from "../ui/button";
import { Label } from "../ui/label";
import { Switch } from "../ui/switch";
import { ContentBlocksPreview } from "./ContentBlocksPreview";
import {
  ArtifactContent,
  ArtifactTitle,
  useArtifactContext,
  useArtifactOpen,
} from "./artifact";
import ThreadHistory from "./history";
import {
  AssistantMessage,
  AssistantMessageLoading,
  DeepResearchLoading,
} from "./messages/ai";
import { HumanMessage } from "./messages/human";
import { ReasoningBlock } from "./reasoning-block";
import { TooltipIconButton } from "./tooltip-icon-button";
import { getContentString } from "./utils";

function StickyToBottomContent(props: {
  content: ReactNode;
  footer?: ReactNode;
  className?: string;
  contentClassName?: string;
}) {
  const context = useStickToBottomContext();
  return (
    <div
      ref={context.scrollRef}
      style={{ width: "100%", height: "100%" }}
      className={props.className}
    >
      <div
        ref={context.contentRef}
        className={props.contentClassName}
      >
        {props.content}
      </div>

      {props.footer}
    </div>
  );
}

function ScrollToBottom(props: { className?: string }) {
  const { isAtBottom, scrollToBottom } = useStickToBottomContext();

  if (isAtBottom) return null;
  return (
    <Button
      variant="outline"
      className={props.className}
      onClick={() => scrollToBottom()}
    >
      <ArrowDown className="h-4 w-4" />
      <span>Scroll to bottom</span>
    </Button>
  );
}

export function Thread() {
  const [artifactContext, setArtifactContext] = useArtifactContext();
  const [artifactOpen, closeArtifact] = useArtifactOpen();

  const [threadId, _setThreadId] = useQueryState("threadId");
  const [chatHistoryOpen, setChatHistoryOpen] = useQueryState(
    "chatHistoryOpen",
    parseAsBoolean.withDefault(false),
  );
  // const [enableToolCalls, setEnableToolCalls] = useQueryState(
  //   "enableToolCalls",
  //   parseAsBoolean.withDefault(false),
  // );
  const [isDeepResearch, setIsDeepResearch] = useQueryState(
    "deepResearch",
    parseAsBoolean.withDefault(false),
  );
  const [input, setInput] = useState("");
  const {
    contentBlocks,
    setContentBlocks,
    // handleFileUpload,
    dropRef,
    removeBlock,
    resetBlocks: _resetBlocks,
    dragOver,
    handlePaste,
  } = useFileUpload();
  // const [firstTokenReceived, setFirstTokenReceived] = useState(false);
  const isLargeScreen = useMediaQuery("(min-width: 1024px)");

  const stream = useStreamContext();
  const messages = stream.messages;

  // const documents =
  //   (stream as any).documents || (stream as any).values?.documents;
  const isLoading = stream.isLoading;

  const lastError = useRef<string | undefined>(undefined);

  const setThreadId = (id: string | null) => {
    _setThreadId(id);

    // close artifact and reset artifact context
    closeArtifact();
    setArtifactContext({});
  };

  useEffect(() => {
    if (!stream.error) {
      lastError.current = undefined;
      return;
    }
    try {
      const message = (stream.error as any).message;
      if (!message || lastError.current === message) {
        // Message has already been logged. do not modify ref, return early.
        return;
      }

      // Message is defined, and it has not been logged yet. Save it, and send the error
      lastError.current = message;
      toast.error("An error occurred. Please try again.", {
        description: (
          <p>
            <strong>Error:</strong> <code>{message}</code>
          </p>
        ),
        richColors: true,
        closeButton: true,
      });
    } catch {
      // no-op
    }
  }, [stream.error]);

  // TODO: this should be part of the useStream hook
  const prevMessageLength = useRef(0);
  useEffect(() => {
    prevMessageLength.current = messages.length;
  }, [messages]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if ((input.trim().length === 0 && contentBlocks.length === 0) || isLoading)
      return;

    const newHumanMessage: Message = {
      id: uuidv4(),
      type: "human",
      content: [
        ...(input.trim().length > 0 ? [{ type: "text", text: input }] : []),
        ...contentBlocks,
      ] as Message["content"],
    };

    const toolMessages = ensureToolCallsHaveResponses(stream.messages);

    const context =
      Object.keys(artifactContext).length > 0 ? artifactContext : undefined;

    stream.submit(
      { messages: [...toolMessages, newHumanMessage], context },
      {
        config: {
          configurable: {
            research_mode: isDeepResearch ? "deep" : "quick",
          },
        },
        streamMode: ["values", "custom", "messages"],
        streamSubgraphs: true,
        streamResumable: true,
        optimisticValues: (prev) => ({
          ...prev,
          context,
          messages: [
            ...(prev.messages ?? []),
            ...toolMessages,
            newHumanMessage,
          ],
        }),
      },
    );

    setInput("");
    setContentBlocks([]);
  };

  const handleRegenerate = (
    parentCheckpoint: Checkpoint | null | undefined,
  ) => {
    // Do this so the loading state is correct
    prevMessageLength.current = prevMessageLength.current - 1;

    stream.submit(undefined, {
      checkpoint: parentCheckpoint,
      streamMode: ["custom", "messages"],
      streamSubgraphs: true,
      streamResumable: true,
    });
  };

  const chatStarted = !!threadId || !!messages.length;
  const hasNoAIOrToolMessages = !messages.find(
    (m) => m.type === "ai" || m.type === "tool",
  );

  // State for incremental updates
  const blocksRef = useRef<{
    blocks: any[];
    currentReasoningBlock: Message[];
    lastProcessedIndex: number;
    lastMessages: Message[];
    lastIsFinalStreaming: boolean;
  }>({
    blocks: [],
    currentReasoningBlock: [],
    lastProcessedIndex: -1,
    lastMessages: [],
    lastIsFinalStreaming: false,
  });

  const groupedBlocks = useMemo(() => {
    const isFinalResponseStreaming =
      (stream as any).isFinalResponseStreaming ||
      (stream as any).values?.isFinalResponseStreaming;

    const isFinalMessage = (message: Message) => {
      if (message.type === "human") return true;
      return (
        message.additional_kwargs?.is_final_response ||
        (isFinalResponseStreaming && message.type === "ai")
      );
    };

    const prev = blocksRef.current;

    const isIncremental =
      messages.length >= prev.lastMessages.length &&
      (prev.lastMessages.length === 0 ||
        messages[0]?.id === prev.lastMessages[0]?.id);

    let startIndex = 0;
    let newBlocks: any[] = [];
    let newCurrentReasoningBlock: Message[] = [];

    if (isIncremental) {
      startIndex = Math.max(0, prev.lastMessages.length - 1);

      newBlocks = [...prev.blocks];
      newCurrentReasoningBlock = [...prev.currentReasoningBlock];

      if (messages.length === prev.lastMessages.length && messages.length > 0) {
        const lastMsg = messages[messages.length - 1];

        if (
          newCurrentReasoningBlock.length > 0 &&
          newCurrentReasoningBlock[newCurrentReasoningBlock.length - 1].id ===
            lastMsg.id
        ) {
          newCurrentReasoningBlock.pop();
        } else if (
          newBlocks.length > 0 &&
          newBlocks[newBlocks.length - 1].type === "message" &&
          newBlocks[newBlocks.length - 1].message.id === lastMsg.id
        ) {
          newBlocks.pop();
        }

        startIndex = messages.length - 1;
      } else if (messages.length > prev.lastMessages.length) {
        startIndex = prev.lastMessages.length;
      }
    } else {
      startIndex = 0;
      newBlocks = [];
      newCurrentReasoningBlock = [];
    }

    for (let i = startIndex; i < messages.length; i++) {
      const message = messages[i];

      if (
        message.id?.startsWith(DO_NOT_RENDER_ID_PREFIX) ||
        getContentString(message.content).trim().startsWith("{") ||
        !(
          getContentString(message.content).trim().length > 0 ||
          ((message as AIMessage).tool_calls?.length ?? 0) > 0 ||
          Object.keys(message.additional_kwargs ?? {}).length > 0
        )
      ) {
        continue;
      }

      if (isFinalMessage(message)) {
        if (newCurrentReasoningBlock.length > 0) {
          if (
            newBlocks.length > 0 &&
            newBlocks[newBlocks.length - 1].type === "reasoning"
          ) {
            const lastBlock = newBlocks[newBlocks.length - 1];
            newBlocks[newBlocks.length - 1] = {
              ...lastBlock,
              messages: [...lastBlock.messages, ...newCurrentReasoningBlock],
            };
          } else {
            newBlocks.push({
              type: "reasoning",
              messages: [...newCurrentReasoningBlock],
            });
          }
          newCurrentReasoningBlock = [];
        }
        newBlocks.push({ type: "message", message });
      } else {
        newCurrentReasoningBlock.push(message);
      }
    }

    blocksRef.current = {
      blocks: newBlocks,
      currentReasoningBlock: newCurrentReasoningBlock,
      lastProcessedIndex: messages.length,
      lastMessages: messages,
      lastIsFinalStreaming: isFinalResponseStreaming,
    };

    const finalBlocks = [...newBlocks];
    if (newCurrentReasoningBlock.length > 0) {
      if (
        finalBlocks.length > 0 &&
        finalBlocks[finalBlocks.length - 1].type === "reasoning"
      ) {
        const lastBlock = finalBlocks[finalBlocks.length - 1];
        finalBlocks[finalBlocks.length - 1] = {
          ...lastBlock,
          messages: [...lastBlock.messages, ...newCurrentReasoningBlock],
        };
      } else {
        finalBlocks.push({
          type: "reasoning",
          messages: newCurrentReasoningBlock,
        });
      }
    }

    return finalBlocks;
  }, [
    messages,
    (stream as any).isFinalResponseStreaming,
    (stream as any).values?.isFinalResponseStreaming,
  ]);

  return (
    <div className="flex h-screen w-full overflow-hidden">
      <div className="relative hidden lg:flex">
        <motion.div
          className="absolute z-20 h-full overflow-hidden border-r bg-white"
          style={{ width: 300 }}
          animate={
            isLargeScreen
              ? { x: chatHistoryOpen ? 0 : -300 }
              : { x: chatHistoryOpen ? 0 : -300 }
          }
          initial={{ x: -300 }}
          transition={
            isLargeScreen
              ? { type: "spring", stiffness: 300, damping: 30 }
              : { duration: 0 }
          }
        >
          <div
            className="relative h-full"
            style={{ width: 300 }}
          >
            <ThreadHistory />
          </div>
        </motion.div>
      </div>

      <div
        className={cn(
          "grid w-full grid-cols-[1fr_0fr] transition-all duration-500",
          artifactOpen && "grid-cols-[3fr_2fr]",
        )}
      >
        <motion.div
          className={cn(
            "relative flex min-w-0 flex-1 flex-col overflow-hidden",
            !chatStarted && "grid-rows-[1fr]",
          )}
          layout={isLargeScreen}
          animate={{
            marginLeft: chatHistoryOpen ? (isLargeScreen ? 300 : 0) : 0,
            width: chatHistoryOpen
              ? isLargeScreen
                ? "calc(100% - 300px)"
                : "100%"
              : "100%",
          }}
          transition={
            isLargeScreen
              ? { type: "spring", stiffness: 300, damping: 30 }
              : { duration: 0 }
          }
        >
          {!chatStarted && (
            <div className="absolute top-0 left-0 z-10 flex w-full items-center justify-between gap-3 p-2 pl-4">
              <div>
                {(!chatHistoryOpen || !isLargeScreen) && (
                  <Button
                    className="hover:bg-gray-100"
                    variant="ghost"
                    onClick={() => setChatHistoryOpen((p) => !p)}
                  >
                    {chatHistoryOpen ? (
                      <PanelRightOpen className="size-5" />
                    ) : (
                      <PanelRightClose className="size-5" />
                    )}
                  </Button>
                )}
              </div>
            </div>
          )}
          {chatStarted && (
            <div className="relative z-10 flex items-center justify-between gap-3 p-2">
              <div className="relative flex items-center justify-start gap-2">
                <div className="absolute left-0 z-10">
                  {(!chatHistoryOpen || !isLargeScreen) && (
                    <Button
                      className="hover:bg-gray-100"
                      variant="ghost"
                      onClick={() => setChatHistoryOpen((p) => !p)}
                    >
                      {chatHistoryOpen ? (
                        <PanelRightOpen className="size-5" />
                      ) : (
                        <PanelRightClose className="size-5" />
                      )}
                    </Button>
                  )}
                </div>
                <motion.button
                  className="flex cursor-pointer items-center gap-2"
                  onClick={() => setThreadId(null)}
                  animate={{
                    marginLeft: !chatHistoryOpen ? 48 : 0,
                  }}
                  transition={{
                    type: "spring",
                    stiffness: 300,
                    damping: 30,
                  }}
                >
                  <NEFACLogoSVG
                    width={32}
                    height={32}
                  />
                  <span className="text-xl font-semibold tracking-tight">
                    NEFAC Chat
                  </span>
                </motion.button>
              </div>

              <div className="flex items-center gap-4">
                <TooltipIconButton
                  size="lg"
                  className="p-4"
                  tooltip="New thread"
                  variant="ghost"
                  onClick={() => setThreadId(null)}
                >
                  <SquarePen className="size-5" />
                </TooltipIconButton>
              </div>

              <div className="from-background to-background/0 absolute inset-x-0 top-full h-5 bg-gradient-to-b" />
            </div>
          )}

          <StickToBottom className="relative flex-1 overflow-hidden">
            <StickyToBottomContent
              className={cn(
                "absolute inset-0 overflow-y-scroll px-4 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-track]:bg-transparent",
                !chatStarted && "mt-[25vh] flex flex-col items-stretch",
                chatStarted && "grid grid-rows-[1fr_auto]",
              )}
              contentClassName="pt-8 pb-16 max-w-3xl mx-auto flex flex-col gap-4 w-full"
              content={
                <>
                  {groupedBlocks.map((block, index) => {
                    if (block.type === "reasoning") {
                      return (
                        <ReasoningBlock
                          key={`reasoning-${index}`}
                          messages={block.messages}
                          isLoading={
                            isLoading && index === groupedBlocks.length - 1
                          }
                          thread={stream}
                        />
                      );
                    }

                    // Check for Deep Research
                    const isDeepResearch = block.message.tool_calls?.some(
                      (tc: any) => tc.name === "deep_research",
                    );
                    if (isDeepResearch) {
                      const isLastBlock = index === groupedBlocks.length - 1;
                      const isResearching =
                        isLoading && !stream.interrupt && isLastBlock;
                      return (
                        <DeepResearchLoading
                          key={index}
                          isComplete={!isResearching}
                        />
                      );
                    }

                    const message = block.message;
                    return (
                      <div
                        key={message.id}
                        className="flex flex-col gap-2"
                      >
                        {message.type === "human" ? (
                          <HumanMessage
                            message={message}
                            isLoading={isLoading}
                          />
                        ) : (
                          <AssistantMessage
                            message={message}
                            isLoading={
                              isLoading && index === groupedBlocks.length - 1
                            }
                            handleRegenerate={handleRegenerate}
                            thread={stream}
                            isLastMessage={
                              message.id === messages[messages.length - 1]?.id
                            }
                            hasNoAIOrToolMessages={
                              !messages.some(
                                (m) => m.type === "ai" || m.type === "tool",
                              )
                            }
                            meta={stream.getMessagesMetadata(message)}
                            interrupt={stream.interrupt}
                          />
                        )}
                      </div>
                    );
                  })}
                  {/* Special rendering case where there are no AI/tool messages, but there is an interrupt.
                    We need to render it outside of the messages list, since there are no messages to render */}
                  {hasNoAIOrToolMessages && !!stream.interrupt && (
                    <AssistantMessage
                      key="interrupt-msg"
                      message={undefined}
                      isLoading={isLoading}
                      handleRegenerate={handleRegenerate}
                      thread={stream}
                      isLastMessage={true}
                      hasNoAIOrToolMessages={true}
                      meta={undefined}
                      interrupt={stream.interrupt}
                    />
                  )}
                  {isLoading && <AssistantMessageLoading />}
                </>
              }
              footer={
                <div className="sticky bottom-0 flex flex-col items-center gap-8 bg-white">
                  {!chatStarted && (
                    <div className="flex items-center gap-3">
                      <NEFACLogoSVG className="h-8 flex-shrink-0" />
                      <h1 className="text-2xl font-semibold tracking-tight">
                        NEFAC Chat
                      </h1>
                    </div>
                  )}

                  <ScrollToBottom className="animate-in fade-in-0 zoom-in-95 absolute bottom-full left-1/2 mb-4 -translate-x-1/2" />

                  <div
                    ref={dropRef}
                    className={cn(
                      "bg-muted relative z-10 mx-auto mb-8 w-full max-w-3xl rounded-2xl shadow-xs transition-all",
                      dragOver
                        ? "border-primary border-2 border-dotted"
                        : "border border-solid",
                    )}
                  >
                    <form
                      onSubmit={handleSubmit}
                      className="mx-auto grid max-w-3xl grid-rows-[1fr_auto] gap-2"
                    >
                      <ContentBlocksPreview
                        blocks={contentBlocks}
                        onRemove={removeBlock}
                      />
                      <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onPaste={handlePaste}
                        onKeyDown={(e) => {
                          if (
                            e.key === "Enter" &&
                            !e.shiftKey &&
                            !e.metaKey &&
                            !e.nativeEvent.isComposing
                          ) {
                            e.preventDefault();
                            const el = e.target as HTMLElement | undefined;
                            const form = el?.closest("form");
                            form?.requestSubmit();
                          }
                        }}
                        placeholder="Type your message..."
                        className="field-sizing-content resize-none border-none bg-transparent p-3.5 pb-0 shadow-none ring-0 outline-none focus:ring-0 focus:outline-none"
                      />

                      <div className="flex items-center gap-6 p-2 pt-4">
                        {/* <div>
                          <div className="flex items-center space-x-2">
                            <Switch
                              id="render-tool-calls"
                              checked={enableToolCalls ?? false}
                              onCheckedChange={setEnableToolCalls}
                            />
                            <Label
                              htmlFor="render-tool-calls"
                              className="text-sm text-gray-600"
                            >
                              Hide Tool Calls
                            </Label>
                          </div>
                        </div> */}
                        <div>
                          <div className="flex items-center space-x-2">
                            <Switch
                              id="deep-research-mode"
                              checked={isDeepResearch ?? false}
                              onCheckedChange={setIsDeepResearch}
                            />
                            <Label
                              htmlFor="deep-research-mode"
                              className="text-sm text-gray-600"
                            >
                              Deep Research
                            </Label>
                          </div>
                        </div>
                        {/* <Label
                          htmlFor="file-input"
                          className="flex cursor-pointer items-center gap-2"
                        >
                          <Plus className="size-5 text-gray-600" />
                          <span className="text-sm text-gray-600">
                            Upload PDF or Image
                          </span>
                        </Label>
                        <input
                          title="Upload PDF or Image"
                          placeholder="Choose PDF or image files"
                          id="file-input"
                          type="file"
                          onChange={handleFileUpload}
                          multiple
                          accept="image/jpeg,image/png,image/gif,image/webp,application/pdf"
                          className="hidden"
                        /> */}
                        {stream.isLoading ? (
                          <Button
                            key="stop"
                            onClick={() => stream.stop()}
                            className="ml-auto"
                          >
                            <LoaderCircle className="h-4 w-4 animate-spin" />
                            Cancel
                          </Button>
                        ) : (
                          <Button
                            type="submit"
                            className="ml-auto shadow-md transition-all"
                            disabled={
                              isLoading ||
                              (!input.trim() && contentBlocks.length === 0)
                            }
                          >
                            Send
                          </Button>
                        )}
                      </div>
                    </form>
                  </div>
                </div>
              }
            />
          </StickToBottom>
        </motion.div>
        <div className="relative flex flex-col border-l">
          <div className="absolute inset-0 flex min-w-[30vw] flex-col">
            <div className="grid grid-cols-[1fr_auto] border-b p-4">
              <ArtifactTitle className="truncate overflow-hidden" />
              <button
                onClick={closeArtifact}
                className="cursor-pointer"
                title="Close Artifact"
              >
                <XIcon className="size-5" />
              </button>
            </div>
            <ArtifactContent className="relative flex-grow" />
          </div>
        </div>
      </div>
    </div>
  );
}
