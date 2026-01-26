"use client";

import { useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import {
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  FileCode,
  Terminal,
  Maximize2,
  Minimize2,
} from "lucide-react";

interface CodeArtifactProps {
  code: string;
  language?: string;
  filename?: string;
  onOpenInEditor?: (code: string, language?: string, filename?: string) => void;
  className?: string;
  maxHeight?: number;
  collapsible?: boolean;
  defaultCollapsed?: boolean;
}

// Detect language from code content
function detectLanguage(code: string): string {
  // Check for common patterns
  if (code.includes("import React") || code.includes("export default function")) return "tsx";
  if (code.includes("import {") && code.includes("from '")) return "typescript";
  if (code.includes("const ") && code.includes(" = {")) return "javascript";
  if (code.includes("def ") && code.includes(":")) return "python";
  if (code.includes("func ") && code.includes("package ")) return "go";
  if (code.includes("fn ") && code.includes("-> ")) return "rust";
  if (code.includes("<template>") || code.includes("<script setup>")) return "vue";
  if (code.includes("<!DOCTYPE html>") || code.includes("<html")) return "html";
  if (code.includes("{%") || code.includes("{{")) return "twig";
  if (code.startsWith("$") || code.includes("#!/bin")) return "bash";
  if (code.includes("SELECT ") || code.includes("CREATE TABLE")) return "sql";
  if (code.includes('{"') || (code.startsWith("{") && code.includes(":"))) return "json";
  if (code.includes("---") && code.includes(":")) return "yaml";
  if (code.includes(".class") || code.includes("@media")) return "css";
  return "text";
}

// Get display name for language
function getLanguageDisplayName(lang: string): string {
  const names: Record<string, string> = {
    typescript: "TypeScript",
    tsx: "TSX",
    javascript: "JavaScript",
    jsx: "JSX",
    python: "Python",
    go: "Go",
    rust: "Rust",
    html: "HTML",
    css: "CSS",
    scss: "SCSS",
    json: "JSON",
    yaml: "YAML",
    bash: "Bash",
    shell: "Shell",
    sql: "SQL",
    twig: "Twig",
    vue: "Vue",
    markdown: "Markdown",
    text: "Text",
  };
  return names[lang] || lang.toUpperCase();
}

export function CodeArtifact({
  code,
  language,
  filename,
  onOpenInEditor,
  className,
  maxHeight = 300,
  collapsible = false,
  defaultCollapsed = false,
}: CodeArtifactProps) {
  const [copied, setCopied] = useState(false);
  const [isExpanded, setIsExpanded] = useState(!defaultCollapsed);
  const [isFullHeight, setIsFullHeight] = useState(false);

  const detectedLanguage = language || detectLanguage(code);
  const lineCount = code.split("\n").length;
  const isLongCode = lineCount > 15;

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [code]);

  const handleOpenInEditor = useCallback(() => {
    onOpenInEditor?.(code, detectedLanguage, filename);
  }, [code, detectedLanguage, filename, onOpenInEditor]);

  const content = (
    <div className={cn("relative group", className)}>
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#282c34] rounded-t-md border-b border-[#3e4451]">
        <div className="flex items-center gap-2 min-w-0">
          <FileCode className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          {filename ? (
            <span className="text-xs text-muted-foreground font-mono truncate">
              {filename}
            </span>
          ) : (
            <Badge variant="secondary" className="text-[9px] h-4 px-1.5 bg-[#3e4451] text-[#abb2bf]">
              {getLanguageDisplayName(detectedLanguage)}
            </Badge>
          )}
          {lineCount > 1 && (
            <span className="text-[10px] text-muted-foreground/60 hidden sm:inline">
              {lineCount} lines
            </span>
          )}
        </div>

        <div className="flex items-center gap-0.5">
          {isLongCode && (
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-muted-foreground hover:text-foreground"
              onClick={() => setIsFullHeight(!isFullHeight)}
              title={isFullHeight ? "Collapse" : "Expand"}
            >
              {isFullHeight ? (
                <Minimize2 className="h-3 w-3" />
              ) : (
                <Maximize2 className="h-3 w-3" />
              )}
            </Button>
          )}
          {onOpenInEditor && (
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-muted-foreground hover:text-foreground"
              onClick={handleOpenInEditor}
              title="Open in Editor"
            >
              <ExternalLink className="h-3 w-3" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 text-muted-foreground hover:text-foreground"
            onClick={handleCopy}
            title="Copy code"
          >
            {copied ? (
              <Check className="h-3 w-3 text-green-500" />
            ) : (
              <Copy className="h-3 w-3" />
            )}
          </Button>
        </div>
      </div>

      {/* Code content */}
      <div
        className={cn(
          "overflow-auto rounded-b-md",
          !isFullHeight && `max-h-[${maxHeight}px]`
        )}
        style={!isFullHeight ? { maxHeight } : undefined}
      >
        <SyntaxHighlighter
          language={detectedLanguage}
          style={oneDark}
          customStyle={{
            margin: 0,
            padding: "12px",
            fontSize: "12px",
            lineHeight: "1.5",
            borderRadius: 0,
            background: "#282c34",
          }}
          showLineNumbers={lineCount > 5}
          lineNumberStyle={{
            minWidth: "2.5em",
            paddingRight: "1em",
            color: "#636d83",
            textAlign: "right",
          }}
        >
          {code}
        </SyntaxHighlighter>
      </div>

      {/* Fade gradient for long code */}
      {!isFullHeight && isLongCode && (
        <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-[#282c34] to-transparent pointer-events-none rounded-b-md" />
      )}
    </div>
  );

  if (collapsible) {
    return (
      <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
        <CollapsibleTrigger asChild>
          <button className="w-full flex items-center gap-2 px-3 py-1.5 bg-[#282c34] rounded-t-md border-b border-[#3e4451] hover:bg-[#3e4451]/50 transition-colors">
            {isExpanded ? (
              <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
            )}
            <FileCode className="h-3.5 w-3.5 text-muted-foreground" />
            {filename ? (
              <span className="text-xs text-muted-foreground font-mono truncate">
                {filename}
              </span>
            ) : (
              <Badge variant="secondary" className="text-[9px] h-4 px-1.5 bg-[#3e4451] text-[#abb2bf]">
                {getLanguageDisplayName(detectedLanguage)}
              </Badge>
            )}
            <span className="text-[10px] text-muted-foreground/60 ml-auto">
              {lineCount} lines
            </span>
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>{content}</CollapsibleContent>
      </Collapsible>
    );
  }

  return content;
}

// Compact inline code badge
export function InlineCode({ children, className }: { children: string; className?: string }) {
  return (
    <code
      className={cn(
        "px-1 py-0.5 rounded bg-muted font-mono text-[0.9em] text-foreground/90",
        className
      )}
    >
      {children}
    </code>
  );
}

// Terminal output display
export function TerminalOutput({ output, className }: { output: string; className?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(output);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={cn("relative group", className)}>
      <div className="flex items-center justify-between px-3 py-1.5 bg-black rounded-t-md border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <Terminal className="h-3.5 w-3.5 text-zinc-500" />
          <span className="text-xs text-zinc-500">Terminal Output</span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 text-zinc-500 hover:text-zinc-300"
          onClick={handleCopy}
        >
          {copied ? (
            <Check className="h-3 w-3 text-green-500" />
          ) : (
            <Copy className="h-3 w-3" />
          )}
        </Button>
      </div>
      <pre className="p-3 bg-black rounded-b-md text-xs text-green-400 font-mono overflow-x-auto max-h-48 overflow-y-auto">
        {output}
      </pre>
    </div>
  );
}
