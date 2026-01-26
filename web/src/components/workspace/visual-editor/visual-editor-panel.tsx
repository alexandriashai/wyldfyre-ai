"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { workspaceApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Save, Upload, Download, RotateCcw, Blocks } from "lucide-react";
import { cn } from "@/lib/utils";
import "grapesjs/dist/css/grapes.min.css";

// Twig syntax preservation helpers
const TWIG_BLOCK_MARKER = 'data-twig-block';
const TWIG_VAR_MARKER = 'data-twig-var';
const TWIG_COMMENT_MARKER = 'data-twig-comment';

function wrapTwigSyntax(html: string): string {
  // Wrap {% ... %} blocks (statements)
  html = html.replace(
    /(\{%[\s\S]*?%\})/g,
    `<span ${TWIG_BLOCK_MARKER}="true" contenteditable="false" style="background:#fef3c7;color:#92400e;padding:2px 4px;border-radius:3px;font-family:monospace;font-size:12px;">$1</span>`
  );

  // Wrap {{ ... }} (variables/expressions)
  html = html.replace(
    /(\{\{[\s\S]*?\}\})/g,
    `<span ${TWIG_VAR_MARKER}="true" contenteditable="false" style="background:#dbeafe;color:#1e40af;padding:2px 4px;border-radius:3px;font-family:monospace;font-size:12px;">$1</span>`
  );

  // Wrap {# ... #} (comments)
  html = html.replace(
    /(\{#[\s\S]*?#\})/g,
    `<span ${TWIG_COMMENT_MARKER}="true" contenteditable="false" style="background:#e5e7eb;color:#6b7280;padding:2px 4px;border-radius:3px;font-family:monospace;font-size:12px;">$1</span>`
  );

  return html;
}

function unwrapTwigSyntax(html: string): string {
  // Remove wrapper spans but keep the Twig content
  html = html.replace(
    new RegExp(`<span\\s+${TWIG_BLOCK_MARKER}="true"[^>]*>([\\s\\S]*?)<\\/span>`, 'g'),
    '$1'
  );
  html = html.replace(
    new RegExp(`<span\\s+${TWIG_VAR_MARKER}="true"[^>]*>([\\s\\S]*?)<\\/span>`, 'g'),
    '$1'
  );
  html = html.replace(
    new RegExp(`<span\\s+${TWIG_COMMENT_MARKER}="true"[^>]*>([\\s\\S]*?)<\\/span>`, 'g'),
    '$1'
  );
  return html;
}

function isTwigFile(path: string): boolean {
  return /\.twig$/i.test(path);
}

interface GrapesJSEditor {
  getHtml: () => string;
  getCss: () => string;
  getJs: () => string;
  setComponents: (html: string) => void;
  setStyle: (css: string) => void;
  on: (event: string, callback: (...args: unknown[]) => void) => void;
  off: (event: string, callback: (...args: unknown[]) => void) => void;
  destroy: () => void;
  DomComponents: {
    getWrapper: () => unknown;
    addComponent: (component: unknown) => void;
  };
  BlockManager: {
    add: (id: string, block: Record<string, unknown>) => void;
    getAll: () => unknown[];
  };
  Panels: {
    addButton: (panelId: string, button: Record<string, unknown>) => void;
  };
  StorageManager: {
    add: (type: string, storage: Record<string, unknown>) => void;
  };
  runCommand: (command: string, options?: Record<string, unknown>) => void;
  store: () => void;
}

export function VisualEditorPanel() {
  const editorRef = useRef<HTMLDivElement>(null);
  const gjsRef = useRef<GrapesJSEditor | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [originalHead, setOriginalHead] = useState<string | null>(null);
  const [originalDoctype, setOriginalDoctype] = useState<string>("<!DOCTYPE html>");
  const [originalHtmlAttrs, setOriginalHtmlAttrs] = useState<string>('lang="en"');

  const { token } = useAuthStore();
  const { activeProjectId, activeFilePath } = useWorkspaceStore();

  // Initialize GrapesJS
  useEffect(() => {
    if (!editorRef.current || gjsRef.current) return;

    const initEditor = async () => {
      try {
        const grapesjs = (await import("grapesjs")).default;

        const editor = grapesjs.init({
          container: editorRef.current!,
          height: "100%",
          width: "auto",
          fromElement: false,
          storageManager: false,
          panels: { defaults: [] },
          deviceManager: {
            devices: [
              { name: "Desktop", width: "" },
              { name: "Tablet", width: "768px", widthMedia: "992px" },
              { name: "Mobile", width: "375px", widthMedia: "480px" },
            ],
          },
          styleManager: {
            sectors: [
              {
                name: "General",
                properties: [
                  "display", "float", "position", "top", "right", "left", "bottom",
                ],
              },
              {
                name: "Dimension",
                properties: [
                  "width", "height", "max-width", "min-height",
                  "margin", "padding",
                ],
              },
              {
                name: "Typography",
                properties: [
                  "font-family", "font-size", "font-weight",
                  "letter-spacing", "color", "line-height",
                  "text-align", "text-decoration", "text-shadow",
                ],
              },
              {
                name: "Decorations",
                properties: [
                  "opacity", "border-radius", "border",
                  "box-shadow", "background", "background-color",
                ],
              },
            ],
          },
          blockManager: {
            blocks: getDefaultBlocks(),
          },
          canvas: {
            styles: [
              "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css",
            ],
          },
        }) as unknown as GrapesJSEditor;

        // Register custom blocks from templates
        registerPlatformBlocks(editor);

        // Track changes
        editor.on("component:update", () => setIsDirty(true));
        editor.on("component:add", () => setIsDirty(true));
        editor.on("component:remove", () => setIsDirty(true));
        editor.on("style:change", () => setIsDirty(true));

        gjsRef.current = editor;
        setIsLoaded(true);
        setStatusMessage("Editor ready");
      } catch (err) {
        console.error("Failed to initialize GrapesJS:", err);
        setStatusMessage("Failed to load editor");
      }
    };

    initEditor();

    return () => {
      if (gjsRef.current) {
        gjsRef.current.destroy();
        gjsRef.current = null;
      }
    };
  }, []);

  // Load current file into editor when activeFilePath changes
  useEffect(() => {
    if (!gjsRef.current || !token || !activeProjectId || !activeFilePath) return;

    // Support HTML and Twig files
    const isEditableFile = /\.(html?|htm|twig)$/i.test(activeFilePath);
    if (!isEditableFile) return;

    loadFileIntoEditor(activeFilePath);
  }, [activeFilePath, token, activeProjectId]);

  const loadFileIntoEditor = useCallback(async (path: string) => {
    if (!token || !activeProjectId || !gjsRef.current) return;

    try {
      setStatusMessage("Loading...");
      const result = await workspaceApi.getFileContent(token, activeProjectId, path);

      if (result.is_binary) {
        setStatusMessage("Cannot edit binary files");
        return;
      }

      // Parse HTML to extract body content and styles
      const parser = new DOMParser();
      const doc = parser.parseFromString(result.content, "text/html");

      // Preserve original head content for saving
      const headContent = doc.head.innerHTML;
      setOriginalHead(headContent);

      // Preserve html attributes (like lang, data-bs-theme, etc.)
      const htmlEl = doc.documentElement;
      const htmlAttrs = Array.from(htmlEl.attributes)
        .map(attr => `${attr.name}="${attr.value}"`)
        .join(' ');
      setOriginalHtmlAttrs(htmlAttrs || 'lang="en"');

      // Preserve doctype
      const doctypeMatch = result.content.match(/^<!DOCTYPE[^>]*>/i);
      if (doctypeMatch) {
        setOriginalDoctype(doctypeMatch[0]);
      }

      let bodyContent = doc.body.innerHTML || result.content;

      // For Twig files, wrap Twig syntax in special elements
      const isTwig = isTwigFile(path);
      if (isTwig) {
        bodyContent = wrapTwigSyntax(bodyContent);
      }

      // Extract inline styles from head for GrapeJS style manager
      const styleElements = doc.head.querySelectorAll("style");
      let css = "";
      styleElements.forEach((el) => {
        css += el.textContent || "";
      });

      gjsRef.current!.setComponents(bodyContent);
      if (css) {
        gjsRef.current!.setStyle(css);
      }

      setActiveFile(path);
      setIsDirty(false);
      setStatusMessage(`Loaded: ${path}`);
    } catch (err) {
      console.error("Failed to load file:", err);
      setStatusMessage("Load failed");
    }
  }, [token, activeProjectId]);

  const handleSave = useCallback(async () => {
    if (!gjsRef.current || !token || !activeProjectId) return;

    const filePath = activeFile || activeFilePath || "index.html";
    let bodyHtml = gjsRef.current.getHtml();
    const css = gjsRef.current.getCss();

    // For Twig files, unwrap the Twig syntax before saving
    if (isTwigFile(filePath)) {
      bodyHtml = unwrapTwigSyntax(bodyHtml);
    }

    let fullHtml: string;

    if (originalHead) {
      // Preserve original document structure, just update body and inline styles
      // Remove old inline styles from head and add new ones
      let headContent = originalHead;
      // Remove existing <style> tags that we'll replace
      headContent = headContent.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '');
      // Add GrapeJS styles at the end of head
      if (css) {
        headContent += `\n  <style>\n${css}\n  </style>`;
      }

      fullHtml = `${originalDoctype}
<html ${originalHtmlAttrs}>
<head>
${headContent}
</head>
<body>
${bodyHtml}
</body>
</html>`;
    } else {
      // No original content, build new document
      fullHtml = buildHtmlDocument(bodyHtml, css);
    }

    try {
      setStatusMessage("Saving...");
      await workspaceApi.writeFileContent(token, activeProjectId, filePath, fullHtml);
      setIsDirty(false);
      setActiveFile(filePath);
      setStatusMessage(`Saved: ${filePath}`);
    } catch (err) {
      console.error("Save failed:", err);
      setStatusMessage("Save failed");
    }
  }, [token, activeProjectId, activeFile, activeFilePath, originalHead, originalDoctype, originalHtmlAttrs]);

  const handleExportHtml = useCallback(() => {
    if (!gjsRef.current) return;

    const html = gjsRef.current.getHtml();
    const css = gjsRef.current.getCss();
    const fullHtml = buildHtmlDocument(html, css);

    const blob = new Blob([fullHtml], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = activeFile || "page.html";
    a.click();
    URL.revokeObjectURL(url);
  }, [activeFile]);

  const handleClear = useCallback(() => {
    if (!gjsRef.current) return;
    gjsRef.current.setComponents("");
    gjsRef.current.setStyle("");
    setIsDirty(true);
    setStatusMessage("Canvas cleared");
  }, []);

  const handleLoadFromFile = useCallback(async () => {
    if (!activeFilePath) {
      setStatusMessage("Select an HTML file in the file tree first");
      return;
    }
    await loadFileIntoEditor(activeFilePath);
  }, [activeFilePath, loadFileIntoEditor]);

  return (
    <div className="flex flex-col h-full relative">
      {/* Loading overlay */}
      {!isLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
          <div className="text-center space-y-2">
            <Blocks className="h-8 w-8 mx-auto opacity-50 animate-pulse" />
            <p className="text-sm text-muted-foreground">Loading Visual Editor...</p>
          </div>
        </div>
      )}
      {/* Toolbar */}
      <div className="flex items-center gap-1 px-2 py-1 border-b bg-muted/30 shrink-0">
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs gap-1"
          onClick={handleSave}
          disabled={!isDirty}
        >
          <Save className="h-3 w-3" />
          Save
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs gap-1"
          onClick={handleLoadFromFile}
        >
          <Upload className="h-3 w-3" />
          Load
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs gap-1"
          onClick={handleExportHtml}
        >
          <Download className="h-3 w-3" />
          Export
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs gap-1"
          onClick={handleClear}
        >
          <RotateCcw className="h-3 w-3" />
          Clear
        </Button>
        <div className="flex-1" />
        <span className={cn(
          "text-[10px] truncate max-w-[150px]",
          isDirty ? "text-yellow-500" : "text-muted-foreground"
        )}>
          {statusMessage}
        </span>
      </div>

      {/* GrapesJS Container */}
      <div ref={editorRef} className="flex-1 min-h-0" />
    </div>
  );
}

function getDefaultBlocks() {
  return [
    {
      id: "section",
      label: "Section",
      category: "Layout",
      content: '<section class="py-5"><div class="container"><div class="row"><div class="col-12"><h2>Section Title</h2><p>Section content goes here.</p></div></div></div></section>',
    },
    {
      id: "hero",
      label: "Hero",
      category: "Layout",
      content: '<section class="py-5 bg-dark text-white text-center"><div class="container"><h1 class="display-4">Hero Title</h1><p class="lead">A compelling subtitle for your page.</p><a href="#" class="btn btn-primary btn-lg mt-3">Get Started</a></div></section>',
    },
    {
      id: "two-columns",
      label: "2 Columns",
      category: "Layout",
      content: '<div class="container py-4"><div class="row"><div class="col-md-6"><h3>Column 1</h3><p>Content for the first column.</p></div><div class="col-md-6"><h3>Column 2</h3><p>Content for the second column.</p></div></div></div>',
    },
    {
      id: "three-columns",
      label: "3 Columns",
      category: "Layout",
      content: '<div class="container py-4"><div class="row"><div class="col-md-4"><h4>Column 1</h4><p>Content.</p></div><div class="col-md-4"><h4>Column 2</h4><p>Content.</p></div><div class="col-md-4"><h4>Column 3</h4><p>Content.</p></div></div></div>',
    },
    {
      id: "card",
      label: "Card",
      category: "Components",
      content: '<div class="card" style="width: 18rem;"><div class="card-body"><h5 class="card-title">Card Title</h5><p class="card-text">Some quick example text.</p><a href="#" class="btn btn-primary">Go somewhere</a></div></div>',
    },
    {
      id: "navbar",
      label: "Navbar",
      category: "Components",
      content: '<nav class="navbar navbar-expand-lg navbar-dark bg-dark"><div class="container"><a class="navbar-brand" href="#">Brand</a><ul class="navbar-nav ms-auto"><li class="nav-item"><a class="nav-link" href="#">Home</a></li><li class="nav-item"><a class="nav-link" href="#">About</a></li><li class="nav-item"><a class="nav-link" href="#">Contact</a></li></ul></div></nav>',
    },
    {
      id: "footer",
      label: "Footer",
      category: "Components",
      content: '<footer class="py-4 bg-dark text-white text-center"><div class="container"><p class="mb-0">&copy; 2024 Your Company. All rights reserved.</p></div></footer>',
    },
    {
      id: "form",
      label: "Contact Form",
      category: "Forms",
      content: '<form class="p-4"><div class="mb-3"><label class="form-label">Name</label><input type="text" class="form-control" placeholder="Your name"></div><div class="mb-3"><label class="form-label">Email</label><input type="email" class="form-control" placeholder="your@email.com"></div><div class="mb-3"><label class="form-label">Message</label><textarea class="form-control" rows="4" placeholder="Your message"></textarea></div><button type="submit" class="btn btn-primary">Send</button></form>',
    },
    {
      id: "heading",
      label: "Heading",
      category: "Basic",
      content: "<h2>Heading Text</h2>",
    },
    {
      id: "paragraph",
      label: "Paragraph",
      category: "Basic",
      content: "<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.</p>",
    },
    {
      id: "image",
      label: "Image",
      category: "Basic",
      content: '<img src="https://via.placeholder.com/350x200" class="img-fluid" alt="Placeholder">',
    },
    {
      id: "button",
      label: "Button",
      category: "Basic",
      content: '<a href="#" class="btn btn-primary">Click Me</a>',
    },
  ];
}

function registerPlatformBlocks(editor: GrapesJSEditor) {
  // Register platform-specific blocks that integrate with the template system
  editor.BlockManager.add("ai-generated", {
    label: "AI Block",
    category: "AI",
    content: '<div class="ai-block p-4 border rounded" data-ai-generated="true"><p>AI-generated content placeholder. Use the Chat panel to generate content for this block.</p></div>',
    attributes: { class: "fa fa-magic" },
  });

  editor.BlockManager.add("dynamic-content", {
    label: "Dynamic Content",
    category: "Data",
    content: '<div class="dynamic-content p-3 bg-light rounded" data-source="" data-field=""><p class="text-muted">[Dynamic: Connect to NocoBase API]</p></div>',
    attributes: { class: "fa fa-database" },
  });
}

function buildHtmlDocument(bodyHtml: string, css: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Page</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
${css}
  </style>
</head>
<body>
${bodyHtml}
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"><\/script>
</body>
</html>`;
}
