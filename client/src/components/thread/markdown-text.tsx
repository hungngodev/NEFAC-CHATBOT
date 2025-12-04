"use client";

import { FC, memo, useState } from "react";
import ReactMarkdown from "react-markdown";

import "katex/dist/katex.min.css";
import { CheckIcon, CopyIcon } from "lucide-react";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import { SyntaxHighlighter } from "@/components/thread/syntax-highlighter";
import { TooltipIconButton } from "@/components/thread/tooltip-icon-button";
import { cn } from "@/lib/utils";

interface CodeHeaderProps {
  language?: string;
  code: string;
}

const useCopyToClipboard = ({
  copiedDuration = 3000,
}: {
  copiedDuration?: number;
} = {}) => {
  const [isCopied, setIsCopied] = useState<boolean>(false);

  const copyToClipboard = (value: string) => {
    if (!value) return;

    navigator.clipboard.writeText(value).then(() => {
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), copiedDuration);
    });
  };

  return { isCopied, copyToClipboard };
};

const CodeHeader: FC<CodeHeaderProps> = ({ language, code }) => {
  const { isCopied, copyToClipboard } = useCopyToClipboard();
  const onCopy = () => {
    if (!code || isCopied) return;
    copyToClipboard(code);
  };

  return (
    <div className="flex items-center justify-between gap-4 rounded-t-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white">
      <span className="lowercase [&>span]:text-xs">{language || "text"}</span>
      <TooltipIconButton
        tooltip="Copy"
        onClick={onCopy}
      >
        {!isCopied && <CopyIcon className="h-4 w-4" />}
        {isCopied && <CheckIcon className="h-4 w-4" />}
      </TooltipIconButton>
    </div>
  );
};

const components: any = {
  h1: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children?: React.ReactNode;
  }) => (
    <h1
      className={cn(
        "mt-2 scroll-m-20 text-4xl font-bold tracking-tight",
        className,
      )}
      {...props}
    >
      {children}
    </h1>
  ),
  h2: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children?: React.ReactNode;
  }) => (
    <h2
      className={cn(
        "mt-10 scroll-m-20 border-b pb-1 text-3xl font-semibold tracking-tight first:mt-0",
        className,
      )}
      {...props}
    >
      {children}
    </h2>
  ),
  h3: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children?: React.ReactNode;
  }) => (
    <h3
      className={cn(
        "mt-8 scroll-m-20 text-2xl font-semibold tracking-tight",
        className,
      )}
      {...props}
    >
      {children}
    </h3>
  ),
  h4: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children?: React.ReactNode;
  }) => (
    <h4
      className={cn(
        "mt-8 scroll-m-20 text-xl font-semibold tracking-tight",
        className,
      )}
      {...props}
    >
      {children}
    </h4>
  ),
  h5: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children?: React.ReactNode;
  }) => (
    <h5
      className={cn(
        "mt-8 scroll-m-20 text-lg font-semibold tracking-tight",
        className,
      )}
      {...props}
    >
      {children}
    </h5>
  ),
  h6: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children?: React.ReactNode;
  }) => (
    <h6
      className={cn(
        "mt-8 scroll-m-20 text-base font-semibold tracking-tight",
        className,
      )}
      {...props}
    >
      {children}
    </h6>
  ),
  p: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children?: React.ReactNode;
  }) => (
    <p
      className={cn("leading-7 [&:not(:first-child)]:mt-6", className)}
      {...props}
    >
      {children}
    </p>
  ),
  ul: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children?: React.ReactNode;
  }) => (
    <ul
      className={cn("my-6 ml-6 list-disc [&>li]:mt-2", className)}
      {...props}
    >
      {children}
    </ul>
  ),
  ol: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children?: React.ReactNode;
  }) => (
    <ol
      className={cn("my-6 ml-6 list-decimal [&>li]:mt-2", className)}
      {...props}
    >
      {children}
    </ol>
  ),
  li: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children?: React.ReactNode;
  }) => (
    <li
      className={cn("mt-2", className)}
      {...props}
    >
      {children}
    </li>
  ),
  code: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children: React.ReactNode;
  }) => {
    const match = /language-(\w+)/.exec(className || "");
    const isInline = !match;

    if (isInline) {
      return (
        <code
          className={cn(
            "bg-muted text-foreground rounded px-1.5 py-0.5 font-mono text-sm font-semibold",
            className,
          )}
          {...props}
        >
          {children}
        </code>
      );
    }

    const language = match[1];
    const code = String(children).replace(/\n$/, "");

    return (
      <div className="not-prose my-4 overflow-hidden rounded-lg border bg-zinc-950 dark:bg-zinc-900">
        <CodeHeader
          language={language}
          code={code}
        />
        <div className="overflow-x-auto">
          <SyntaxHighlighter
            language={language}
            className={className}
          >
            {code}
          </SyntaxHighlighter>
        </div>
      </div>
    );
  },
  a: ({
    className,
    children,
    href,
    ...props
  }: {
    className?: string;
    children: React.ReactNode;
    href?: string;
  }) => {
    const isExternal = href?.startsWith("http");
    return (
      <a
        className={cn(
          "font-medium text-blue-600 underline underline-offset-4 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300",
          className,
        )}
        href={href}
        target={isExternal ? "_blank" : undefined}
        rel={isExternal ? "noopener noreferrer" : undefined}
        {...props}
      >
        {children}
      </a>
    );
  },
  table: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children: React.ReactNode;
  }) => (
    <div className="my-6 w-full overflow-y-auto rounded-lg border">
      <table
        className={cn("w-full text-sm", className)}
        {...props}
      >
        {children}
      </table>
    </div>
  ),
  thead: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children: React.ReactNode;
  }) => (
    <thead
      className={cn("bg-muted/50", className)}
      {...props}
    >
      {children}
    </thead>
  ),
  tbody: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children: React.ReactNode;
  }) => (
    <tbody
      className={cn("[&_tr:last-child]:border-0", className)}
      {...props}
    >
      {children}
    </tbody>
  ),
  tfoot: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children: React.ReactNode;
  }) => (
    <tfoot
      className={cn("bg-muted/50 text-muted-foreground font-medium", className)}
      {...props}
    >
      {children}
    </tfoot>
  ),
  th: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children: React.ReactNode;
  }) => (
    <th
      className={cn(
        "text-muted-foreground border-b px-4 py-3 text-left font-medium [&[align=center]]:text-center [&[align=right]]:text-right",
        className,
      )}
      {...props}
    >
      {children}
    </th>
  ),
  td: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children: React.ReactNode;
  }) => (
    <td
      className={cn(
        "border-b px-4 py-3 text-left [&[align=center]]:text-center [&[align=right]]:text-right",
        className,
      )}
      {...props}
    >
      {children}
    </td>
  ),
  tr: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children: React.ReactNode;
  }) => (
    <tr
      className={cn("even:bg-muted/10 m-0 border-t p-0", className)}
      {...props}
    >
      {children}
    </tr>
  ),
  img: ({ className, alt, ...props }: { className?: string; alt?: string }) => (
    <img
      className={cn("bg-muted rounded-lg border", className)}
      alt={alt}
      {...props}
    />
  ),
  hr: ({ className, ...props }: { className?: string }) => (
    <hr
      className={cn("border-muted my-8", className)}
      {...props}
    />
  ),
  blockquote: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children: React.ReactNode;
  }) => (
    <blockquote
      className={cn(
        "border-primary text-muted-foreground mt-6 border-l-2 pl-6 italic",
        className,
      )}
      {...props}
    >
      {children}
    </blockquote>
  ),
  pre: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children: React.ReactNode;
  }) => (
    <pre
      className={cn(
        "bg-muted mt-6 mb-4 overflow-x-auto rounded-lg py-4",
        className,
      )}
      {...props}
    >
      {children}
    </pre>
  ),
  sup: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children: React.ReactNode;
  }) => (
    <sup
      className={cn("[&>a]:text-xs [&>a]:no-underline", className)}
      {...props}
    >
      {children}
    </sup>
  ),
  strong: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children: React.ReactNode;
  }) => (
    <strong
      className={cn("font-bold", className)}
      {...props}
    >
      {children}
    </strong>
  ),
  em: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children: React.ReactNode;
  }) => (
    <em
      className={cn("italic", className)}
      {...props}
    >
      {children}
    </em>
  ),
  del: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children: React.ReactNode;
  }) => (
    <del
      className={cn("line-through", className)}
      {...props}
    >
      {children}
    </del>
  ),
  input: ({
    className,
    type,
    ...props
  }: {
    className?: string;
    type?: string;
  }) => {
    if (type === "checkbox") {
      return (
        <input
          type="checkbox"
          className={cn("mr-2 align-middle", className)}
          disabled
          {...props}
        />
      );
    }
    return (
      <input
        type={type}
        className={className}
        {...props}
      />
    );
  },
  section: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children: React.ReactNode;
  }) => (
    <section
      className={cn(
        "text-muted-foreground mt-8 border-t pt-4 text-sm",
        className,
      )}
      {...props}
    >
      {children}
    </section>
  ),
};

const MarkdownTextImpl: FC<{ children: string }> = ({ children }) => {
  return (
    <div className="markdown-content text-foreground max-w-none break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={components}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
};

export const MarkdownText = memo(MarkdownTextImpl);
