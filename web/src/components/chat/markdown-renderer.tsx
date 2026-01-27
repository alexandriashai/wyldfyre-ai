"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CodeArtifact, InlineCode } from "./code-artifact";

interface MarkdownRendererProps {
  content: string;
  onOpenInEditor?: (code: string, language?: string) => void;
  className?: string;
}

/**
 * Reusable markdown renderer with full GFM support.
 * Includes tables, task lists, strikethrough, syntax highlighting, and more.
 */
export function MarkdownRenderer({
  content,
  onOpenInEditor,
  className,
}: MarkdownRendererProps) {
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            const codeString = String(children).replace(/\n$/, "");
            const isMultiline = codeString.includes("\n") || codeString.length > 80;

            // Inline code
            if (!match && !isMultiline) {
              return <InlineCode>{codeString}</InlineCode>;
            }

            // Code block - use CodeArtifact
            return (
              <CodeArtifact
                code={codeString}
                language={match?.[1]}
                onOpenInEditor={onOpenInEditor}
                className="my-2 -mx-1 sm:mx-0"
                maxHeight={250}
              />
            );
          },
          // Make links more touch-friendly on mobile
          a({ href, children }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline inline-flex items-center gap-0.5"
              >
                {children}
              </a>
            );
          },
          // Tables with proper styling
          table({ children }) {
            return (
              <div className="overflow-x-auto my-3">
                <table className="min-w-full divide-y divide-border border border-border rounded-md text-sm">
                  {children}
                </table>
              </div>
            );
          },
          thead({ children }) {
            return <thead className="bg-muted/50">{children}</thead>;
          },
          th({ children }) {
            return (
              <th className="px-3 py-2 text-left text-xs font-semibold text-foreground">
                {children}
              </th>
            );
          },
          td({ children }) {
            return (
              <td className="px-3 py-2 text-muted-foreground border-t border-border">
                {children}
              </td>
            );
          },
          // Headers with proper sizing
          h1({ children }) {
            return <h1 className="text-xl font-bold mt-4 mb-2 first:mt-0">{children}</h1>;
          },
          h2({ children }) {
            return <h2 className="text-lg font-bold mt-3 mb-2 first:mt-0">{children}</h2>;
          },
          h3({ children }) {
            return <h3 className="text-base font-semibold mt-2 mb-1 first:mt-0">{children}</h3>;
          },
          h4({ children }) {
            return <h4 className="text-sm font-semibold mt-2 mb-1 first:mt-0">{children}</h4>;
          },
          // Lists with proper styling
          ul({ children }) {
            return <ul className="list-disc list-inside my-2 space-y-1">{children}</ul>;
          },
          ol({ children }) {
            return <ol className="list-decimal list-inside my-2 space-y-1">{children}</ol>;
          },
          li({ children }) {
            return <li className="text-muted-foreground">{children}</li>;
          },
          // Blockquotes
          blockquote({ children }) {
            return (
              <blockquote className="border-l-4 border-primary/30 pl-4 my-2 italic text-muted-foreground">
                {children}
              </blockquote>
            );
          },
          // Horizontal rule
          hr() {
            return <hr className="my-4 border-border" />;
          },
          // Paragraphs
          p({ children }) {
            return <p className="my-1.5 first:mt-0 last:mb-0">{children}</p>;
          },
          // Task lists (GFM)
          input({ checked, type }) {
            if (type === "checkbox") {
              return (
                <input
                  type="checkbox"
                  checked={checked}
                  disabled
                  className="mr-2 accent-primary"
                />
              );
            }
            return null;
          },
          // Strong/bold
          strong({ children }) {
            return <strong className="font-semibold text-foreground">{children}</strong>;
          },
          // Emphasis/italic
          em({ children }) {
            return <em className="italic">{children}</em>;
          },
          // Strikethrough (GFM)
          del({ children }) {
            return <del className="line-through text-muted-foreground">{children}</del>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

/**
 * Simplified markdown renderer for streaming content (no code editor support)
 */
export function StreamingMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ className, children }) {
          const codeString = String(children).replace(/\n$/, "");
          return <InlineCode>{codeString}</InlineCode>;
        },
        a({ href, children }) {
          return (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              {children}
            </a>
          );
        },
        // Basic formatting only for streaming
        strong({ children }) {
          return <strong className="font-semibold text-foreground">{children}</strong>;
        },
        em({ children }) {
          return <em className="italic">{children}</em>;
        },
        p({ children }) {
          return <p className="my-1">{children}</p>;
        },
        ul({ children }) {
          return <ul className="list-disc list-inside my-1">{children}</ul>;
        },
        ol({ children }) {
          return <ol className="list-decimal list-inside my-1">{children}</ol>;
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
