"use client";

import { useState, useMemo } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import { Search, Command as CommandIcon, ChevronRight, ChevronDown } from "lucide-react";
import { COMMANDS, Command, CommandSubcommand } from "./command-suggestions";

interface CommandReferenceModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandReferenceModal({
  open,
  onOpenChange,
}: CommandReferenceModalProps) {
  const [searchQuery, setSearchQuery] = useState("");

  const filteredCommands = useMemo(() => {
    if (!searchQuery.trim()) return COMMANDS;

    const query = searchQuery.toLowerCase();
    return COMMANDS.filter((cmd) => {
      // Match command name, description, or aliases
      if (cmd.name.toLowerCase().includes(query)) return true;
      if (cmd.description.toLowerCase().includes(query)) return true;
      if (cmd.aliases.some((a) => a.toLowerCase().includes(query))) return true;

      // Match subcommands
      if (cmd.subcommands) {
        return cmd.subcommands.some(
          (sub) =>
            sub.command.toLowerCase().includes(query) ||
            sub.description.toLowerCase().includes(query)
        );
      }

      return false;
    });
  }, [searchQuery]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CommandIcon className="h-5 w-5" />
            Command Reference
          </DialogTitle>
        </DialogHeader>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search commands..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>

        {/* Command list */}
        <ScrollArea className="flex-1 -mx-6 px-6">
          {filteredCommands.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              <p>No commands found matching "{searchQuery}"</p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredCommands.map((command) => (
                <CommandItem key={command.name} command={command} />
              ))}
            </div>
          )}
        </ScrollArea>

        {/* Footer hint */}
        <div className="pt-4 border-t text-xs text-muted-foreground">
          <p>
            Type <code className="px-1 py-0.5 bg-muted rounded">/</code> in the
            chat input to see command suggestions as you type.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}

interface CommandItemProps {
  command: Command;
}

function CommandItem({ command }: CommandItemProps) {
  const [isOpen, setIsOpen] = useState(false);
  const Icon = command.icon;
  const hasSubcommands = command.subcommands && command.subcommands.length > 0;

  if (!hasSubcommands) {
    // Simple command without subcommands
    return (
      <div className="border rounded-lg p-4 bg-card hover:bg-accent/50 transition-colors">
        <div className="flex items-start gap-3">
          <div className="rounded-md p-2 bg-primary/10 text-primary shrink-0">
            <Icon className="h-4 w-4" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <code className="font-semibold text-sm bg-muted px-2 py-0.5 rounded">
                {command.usage}
              </code>
              {command.aliases.map((alias) => (
                <Badge key={alias} variant="outline" className="text-xs">
                  /{alias}
                </Badge>
              ))}
            </div>
            <p className="text-sm text-muted-foreground mt-1">
              {command.description}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Command with subcommands - use collapsible
  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div className="border rounded-lg bg-card overflow-hidden">
        <CollapsibleTrigger className="w-full px-4 py-3 hover:bg-accent/50 transition-colors">
          <div className="flex items-center gap-3 text-left">
            <div className="rounded-md p-2 bg-primary/10 text-primary shrink-0">
              <Icon className="h-4 w-4" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <code className="font-semibold text-sm bg-muted px-2 py-0.5 rounded">
                  /{command.name}
                </code>
                {command.aliases.map((alias) => (
                  <Badge key={alias} variant="outline" className="text-xs">
                    /{alias}
                  </Badge>
                ))}
                <Badge variant="secondary" className="text-xs">
                  {command.subcommands!.length} subcommands
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground mt-1">
                {command.description}
              </p>
            </div>
            {isOpen ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
            )}
          </div>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="px-4 pb-4 border-t pt-3 bg-muted/30">
            <div className="ml-11 space-y-2 max-h-[300px] overflow-y-auto pr-2">
              {command.subcommands!.map((sub) => (
                <SubcommandItem key={sub.command} subcommand={sub} />
              ))}
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

interface SubcommandItemProps {
  subcommand: CommandSubcommand;
}

function SubcommandItem({ subcommand }: SubcommandItemProps) {
  return (
    <div className="flex items-start gap-2 p-2 rounded-md hover:bg-muted/50 transition-colors">
      <ChevronRight className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
      <div className="flex-1 min-w-0">
        <code className="text-sm font-medium">{subcommand.command}</code>
        <p className="text-xs text-muted-foreground">{subcommand.description}</p>
        {subcommand.usage && (
          <p className="text-xs text-muted-foreground/70 mt-1 font-mono">
            Usage: {subcommand.usage}
          </p>
        )}
      </div>
    </div>
  );
}
