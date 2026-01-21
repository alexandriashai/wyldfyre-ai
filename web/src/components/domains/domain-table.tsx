"use client";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Globe, Lock, Upload, Trash2, ExternalLink } from "lucide-react";

interface Domain {
  id: string;
  domain_name: string;
  status: string;
  ssl_enabled: boolean;
  ssl_expires_at: string | null;
  created_at: string;
}

interface DomainTableProps {
  domains: Domain[];
  onDeploy?: (name: string) => void;
  onDelete?: (name: string) => void;
}

const statusColors: Record<string, string> = {
  active: "bg-green-500/10 text-green-500",
  pending: "bg-yellow-500/10 text-yellow-500",
  suspended: "bg-red-500/10 text-red-500",
  deleted: "bg-gray-500/10 text-gray-500",
};

export function DomainTable({ domains, onDeploy, onDelete }: DomainTableProps) {
  if (domains.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
        <Globe className="h-12 w-12 mb-4 opacity-50" />
        <p>No domains configured</p>
        <p className="text-sm">Add a domain to get started</p>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Domain</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>SSL</TableHead>
          <TableHead>Created</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {domains.map((domain) => (
          <TableRow key={domain.id}>
            <TableCell>
              <div className="flex items-center gap-2">
                <Globe className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">{domain.domain_name}</span>
                <a
                  href={`https://${domain.domain_name}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-muted-foreground hover:text-foreground"
                >
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </TableCell>
            <TableCell>
              <Badge variant="outline" className={cn(statusColors[domain.status])}>
                {domain.status}
              </Badge>
            </TableCell>
            <TableCell>
              <div className="flex items-center gap-1">
                <Lock className={cn("h-3 w-3", domain.ssl_enabled ? "text-green-500" : "text-muted-foreground")} />
                <Badge variant="outline" className={cn(domain.ssl_enabled ? "text-green-500 border-green-500/50" : "text-muted-foreground")}>
                  {domain.ssl_enabled ? "Active" : "Inactive"}
                </Badge>
              </div>
            </TableCell>
            <TableCell className="text-muted-foreground">
              {new Date(domain.created_at).toLocaleDateString()}
            </TableCell>
            <TableCell className="text-right">
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onDeploy?.(domain.domain_name)}
                >
                  <Upload className="h-4 w-4 mr-1" />
                  Deploy
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-destructive hover:text-destructive"
                  onClick={() => onDelete?.(domain.domain_name)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
