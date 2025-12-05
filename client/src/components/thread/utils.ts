import type { Message } from "@langchain/langgraph-sdk";

/**
 * Extracts a string summary from a message's content, supporting multimodal (text, image, file, etc.).
 * - If text is present, returns the joined text.
 * - If not, returns a label for the first non-text modality (e.g., 'Image', 'Other').
 * - If unknown, returns 'Multimodal message'.
 */
export function getContentString(content: Message["content"]): string {
  if (typeof content === "string") return content;
  const texts = content
    .filter((c): c is { type: "text"; text: string } => c.type === "text")
    .map((c) => c.text);
  return texts.join(" ");
}

export function parseDocumentContent(content: string) {
  const parts = {
    context: "",
    summary: "",
    original: content,
  };

  // Format: "Context: ... | Summary ... Chunk: Contextual Summary: ... Original Chunk: ..."
  
  // 1. Extract "Contextual Summary" (specific to the chunk)
  // It starts with "Chunk: Contextual Summary:" or just "Contextual Summary:"
  const summaryMatch = content.match(
    /(?:Chunk:\s*)?Contextual Summary:\s*([\s\S]*?)(?=Original Chunk:|$)/i
  );

  // 2. Extract "Context" (Section Summary / Document Context)
  // It starts with "Context:" and goes until "Chunk:" or "Contextual Summary:"
  const contextMatch = content.match(
    /Context:\s*([\s\S]*?)(?=(?:Chunk:\s*)?Contextual Summary:|$)/i
  );

  // 3. Extract "Original Chunk"
  const originalMatch = content.match(/Original Chunk:\s*([\s\S]*)/i);

  if (contextMatch) parts.context = contextMatch[1].trim();
  if (summaryMatch) parts.summary = summaryMatch[1].trim();
  if (originalMatch) parts.original = originalMatch[1].trim();

  // If no headers found, return content as original
  if (!contextMatch && !summaryMatch && !originalMatch) {
    return parts;
  }

  return parts;
}

export function getEnhancedUrl(
  url: string | undefined,
  content: string,
  metadata?: any
) {
  if (!url) return undefined;

  // YouTube timestamp
  if (url.includes("youtube.com") || url.includes("youtu.be")) {
    if (metadata?.start_time !== undefined) {
      const separator = url.includes("?") ? "&" : "?";
      return `${url}${separator}t=${Math.floor(metadata.start_time)}s`;
    }
    return url;
  }

  // HTML Text Fragment
  // Use the first few words of the content to create a text fragment
  // Clean content: remove newlines and extra spaces
  const cleanContent = content.replace(/\s+/g, " ").trim();
  const words = cleanContent.split(" ").slice(0, 6).join(" ");
  
  if (words.length > 10) {
    const fragment = `#:~:text=${encodeURIComponent(words)}`;
    return `${url}${fragment}`;
  }

  return url;
}
