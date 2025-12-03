import { useState, useEffect, useRef } from "react";
import { ChevronDown, ChevronRight, BrainCircuit } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Message } from "@langchain/langgraph-sdk";
import { AssistantMessage } from "./messages/ai";

interface ReasoningBlockProps {
  messages: Message[];
  isLoading?: boolean;
}

export function ReasoningBlock({ messages, isLoading }: ReasoningBlockProps) {
  const [isOpen, setIsOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen]);

  if (!messages.length) return null;

  return (
    <div className="w-full max-w-3xl mx-auto my-2">
      <Collapsible
        open={isOpen}
        onOpenChange={setIsOpen}
        className="w-full border rounded-lg bg-muted/30"
      >
        <div className="flex items-center justify-between px-4 py-2">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <BrainCircuit className="w-4 h-4" />
            <span className="font-medium">Reasoning Process</span>
            <span className="text-xs opacity-70">({messages.length} steps)</span>
          </div>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="w-9 p-0">
              {isOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
              <span className="sr-only">Toggle reasoning</span>
            </Button>
          </CollapsibleTrigger>
        </div>
        <CollapsibleContent>
          <ScrollArea className="h-[300px] w-full rounded-b-lg border-t bg-muted/10 p-4">
            <div className="flex flex-col gap-4">
              {messages.map((message, index) => (
                <div key={message.id || index} className="text-sm text-muted-foreground">
                  <AssistantMessage
                    message={message}
                    isLoading={false} // Don't show loading spinners inside reasoning
                    handleRegenerate={() => {}} // Disable regen inside reasoning
                  />
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}
