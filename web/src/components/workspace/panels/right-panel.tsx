"use client";

import { PreviewPanel } from "../preview/preview-panel";

export function RightPanel() {
  return (
    <div className="flex flex-col h-full bg-card">
      <PreviewPanel />
    </div>
  );
}
