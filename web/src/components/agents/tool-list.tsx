"use client";

import { cn } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ToolInfo } from "@/lib/api";
import {
  FileCode,
  GitBranch,
  Database,
  Container,
  Network,
  Shield,
  Terminal,
  Search,
  Loader2,
} from "lucide-react";

interface ToolListProps {
  tools: ToolInfo[];
  isLoading?: boolean;
}

const CATEGORY_ICONS: Record<string, React.ElementType> = {
  file: FileCode,
  git: GitBranch,
  database: Database,
  docker: Container,
  network: Network,
  security: Shield,
  system: Terminal,
  general: Search,
};

const CATEGORY_COLORS: Record<string, string> = {
  file: "bg-blue-500/10 text-blue-500",
  git: "bg-orange-500/10 text-orange-500",
  database: "bg-green-500/10 text-green-500",
  docker: "bg-cyan-500/10 text-cyan-500",
  network: "bg-purple-500/10 text-purple-500",
  security: "bg-red-500/10 text-red-500",
  system: "bg-yellow-500/10 text-yellow-500",
  general: "bg-gray-500/10 text-gray-500",
};

const PERMISSION_LABELS: Record<number, { label: string; color: string }> = {
  0: { label: "Read Only", color: "bg-green-500/10 text-green-600" },
  1: { label: "Read/Write", color: "bg-blue-500/10 text-blue-600" },
  2: { label: "Execute", color: "bg-yellow-500/10 text-yellow-600" },
  3: { label: "Admin", color: "bg-orange-500/10 text-orange-600" },
  4: { label: "Superuser", color: "bg-red-500/10 text-red-600" },
};

export function ToolList({ tools, isLoading }: ToolListProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (tools.length === 0) {
    return (
      <div className="rounded-md border p-8 text-center text-muted-foreground">
        No tools configured for this agent
      </div>
    );
  }

  // Group tools by category
  const groupedTools = tools.reduce((acc, tool) => {
    const category = tool.category || "general";
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(tool);
    return acc;
  }, {} as Record<string, ToolInfo[]>);

  return (
    <div className="space-y-6">
      {Object.entries(groupedTools).map(([category, categoryTools]) => {
        const Icon = CATEGORY_ICONS[category] || Search;
        const colorClass = CATEGORY_COLORS[category] || CATEGORY_COLORS.general;

        return (
          <div key={category}>
            <div className="flex items-center gap-2 mb-3">
              <div className={cn("rounded-md p-1.5", colorClass)}>
                <Icon className="h-4 w-4" />
              </div>
              <h3 className="text-sm font-semibold capitalize">{category}</h3>
              <Badge variant="outline" className="text-xs">
                {categoryTools.length}
              </Badge>
            </div>

            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {categoryTools.map((tool) => {
                const permInfo = PERMISSION_LABELS[tool.permission_level] || PERMISSION_LABELS[0];

                return (
                  <Card key={tool.name} className="hover:border-primary/50 transition-colors">
                    <CardHeader className="pb-2">
                      <div className="flex items-start justify-between">
                        <CardTitle className="text-sm font-medium">
                          {tool.name.replace(/_/g, " ")}
                        </CardTitle>
                        <Badge
                          variant="outline"
                          className={cn("text-xs shrink-0", permInfo.color)}
                        >
                          {permInfo.label}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <CardDescription className="text-xs line-clamp-2">
                        {tool.description}
                      </CardDescription>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
