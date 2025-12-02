import { useState } from "react";
import { getEnhancedUrl, parseDocumentContent } from "../utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ChevronDown,
  ChevronUp,
  FileText,
  ExternalLink,
  Info,
  ChevronRight,
  PlayCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

interface DocumentListProps {
  documents: any[];
}

function DocumentChunk({
  doc,
  url,
  index,
}: {
  doc: any;
  url?: string;
  index: number;
}) {
  const { context, summary, original } = parseDocumentContent(doc.page_content);
  
  // Format original content for YouTube: replace newlines with spaces
  const displayOriginal = doc.metadata?.file_type === "youtube" 
    ? original.replace(/\n+/g, " ") 
    : original;

  const enhancedUrl = getEnhancedUrl(url, original, doc.metadata);
  const [isContextOpen, setIsContextOpen] = useState(false);
  
  return (
    <div
      className={cn(
        "flex flex-col gap-3 text-sm",
        index > 0 && "pt-4 border-t border-dashed"
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {/* Score removed as per user request */}
        </div>
        {(context || summary) && (
          <button
            onClick={() => setIsContextOpen(!isContextOpen)}
            className="flex items-center gap-1 text-[10px] font-medium text-muted-foreground hover:text-foreground transition-colors ml-auto"
          >
            {isContextOpen ? (
              <ChevronDown className="size-3" />
            ) : (
              <ChevronRight className="size-3" />
            )}
            {isContextOpen ? "Hide Context" : "Show Context"}
          </button>
        )}
      </div>

      {isContextOpen && (
        <div className="animate-in fade-in slide-in-from-top-1 duration-200 space-y-2">
          {/* 1. Contextual Summary (Chunk specific) */}
          {summary && (
            <div className="bg-muted/50 rounded-md p-2.5 border">
              <div className="flex items-center gap-1.5 mb-1.5">
                <Info className="size-3 text-muted-foreground" />
                <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                  Contextual Summary
                </span>
              </div>
              <div className="text-xs text-muted-foreground leading-relaxed prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-li:my-0 [&_ul]:list-disc [&_ul]:pl-4">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{summary}</ReactMarkdown>
              </div>
            </div>
          )}

          {/* 2. Section Summary (Document/Section context) */}
          {(doc.metadata?.section_summary || context) && (
            <div className="bg-muted/50 rounded-md p-2.5 border">
              <div className="flex items-center gap-1.5 mb-1.5">
                <Info className="size-3 text-muted-foreground" />
                <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                  Section Summary
                </span>
              </div>
              <div className="text-xs text-muted-foreground leading-relaxed prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-li:my-0 [&_ul]:list-disc [&_ul]:pl-4">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {doc.metadata?.section_summary || context}
                </ReactMarkdown>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="relative group">
        <div className="bg-muted/30 rounded-lg border border-border/50 p-4">
          <div className="text-sm text-foreground leading-relaxed font-medium prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-li:my-0 [&_ul]:list-disc [&_ul]:pl-4">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayOriginal}</ReactMarkdown>
          </div>
        </div>
        
        {url && (
          <div className="flex justify-end mt-2">
            <a
              href={enhancedUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors hover:bg-muted rounded-md border border-transparent hover:border-border"
              title={doc.metadata?.file_type === "youtube" ? "Watch Video" : "View Source"}
            >
              {doc.metadata?.file_type === "youtube" ? (
                <>
                  <PlayCircle className="size-3.5" />
                  <span>Watch Video</span>
                </>
              ) : (
                <>
                  <ExternalLink className="size-3.5" />
                  <span>View Source</span>
                </>
              )}
            </a>
          </div>
        )}
      </div>
    </div>
  );
}

export function DocumentList({ documents }: DocumentListProps) {
  const [isOpen, setIsOpen] = useState(false);

  console.log("Documents in DocumentList:", documents);

  if (!documents || documents.length === 0) return null;

  // Group documents by source (URL or Title)
  const groupedDocs = documents.reduce((acc: any, doc: any) => {
    // Parse content to check original chunk length
    const { original } = parseDocumentContent(doc.page_content || "");
    
    // Filter out chunks where original content is less than 10 characters
    if (!original || original.trim().length < 10) {
      return acc;
    }

    // Prioritize source_url, then link, then url, then title
    const url = doc.metadata?.source_url || doc.metadata?.link || doc.metadata?.url;
    const title = doc.metadata?.title || doc.metadata?.document_title || "Unknown Source";
    
    // Use URL as key if available, otherwise title
    const key = url || title;
    
    if (!acc[key]) {
      acc[key] = {
        meta: doc.metadata,
        chunks: [],
        title: title,
        url: url
      };
    }
    acc[key].chunks.push(doc);
    return acc;
  }, {});

  const sources = Object.values(groupedDocs);
  const totalSources = sources.length;

  if (totalSources === 0) return null;

  if (!isOpen) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => setIsOpen(true)}
        className="mt-2 gap-2 text-muted-foreground hover:text-foreground"
      >
        <FileText className="size-4" />
        View {totalSources} {totalSources === 1 ? "Source" : "Sources"}
        <ChevronDown className="size-4" />
      </Button>
    );
  }

  return (
    <div className="mt-4 flex flex-col gap-4 animate-in fade-in slide-in-from-top-2 duration-300">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold text-gray-600">
          <FileText className="size-4" />
          <span>Sources</span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsOpen(false)}
          className="h-8 w-8 p-0"
        >
          <ChevronUp className="size-4" />
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {sources.map((source: any, i: number) => {
          const { title, url } = source;

          return (
            <Card key={i} className="overflow-hidden border-l-4 border-l-primary/20">
              <CardHeader className="bg-muted/30 p-3 pb-2">
                <CardTitle className="text-sm font-medium flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 truncate">
                    <span className="truncate" title={title}>
                      {title}
                    </span>
                    {source.chunks[0]?.metadata?.file_type && (
                      <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-5 uppercase flex-shrink-0">
                        {source.chunks[0].metadata.file_type}
                      </Badge>
                    )}
                    {source.meta?.date && (
                      <span className="text-[10px] text-muted-foreground flex-shrink-0">
                        {source.meta.date}
                      </span>
                    )}
                  </div>
                  {url && (
                    <a
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-muted-foreground hover:text-primary flex-shrink-0"
                      title="Open Link"
                    >
                      <ExternalLink className="size-3.5" />
                    </a>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 flex flex-col gap-1">
                {source.chunks.map((doc: any, j: number) => (
                  <DocumentChunk key={j} doc={doc} url={url} index={j} />
                ))}
              </CardContent>
            </Card>
          );
        })}
      </div>
      
      {sources.length > 0 && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsOpen(false)}
          className="self-center text-xs text-muted-foreground hover:text-foreground mt-2"
        >
          <ChevronUp className="size-3 mr-1" />
          Collapse Sources
        </Button>
      )}
    </div>
  );
}
