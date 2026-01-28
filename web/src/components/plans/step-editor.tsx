"use client";

import { useState } from "react";
import { StepProgress } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Save, X, Plus, Trash2 } from "lucide-react";

interface StepEditorProps {
  step?: StepProgress;
  onSave: (data: Partial<StepProgress>) => Promise<void>;
  onCancel: () => void;
}

const AGENTS = [
  { value: "code", label: "Code" },
  { value: "data", label: "Data" },
  { value: "infra", label: "Infra" },
  { value: "research", label: "Research" },
  { value: "qa", label: "QA" },
  { value: "wyld", label: "Wyld" },
];

export function StepEditor({ step, onSave, onCancel }: StepEditorProps) {
  const [title, setTitle] = useState(step?.title || "");
  const [description, setDescription] = useState(step?.description || "");
  const [agent, setAgent] = useState(step?.agent || "");
  const [todos, setTodos] = useState<string[]>(
    step?.todos?.map((t) => (typeof t === "string" ? t : t.text)) || []
  );
  const [newTodo, setNewTodo] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const handleAddTodo = () => {
    if (newTodo.trim()) {
      setTodos([...todos, newTodo.trim()]);
      setNewTodo("");
    }
  };

  const handleRemoveTodo = (index: number) => {
    setTodos(todos.filter((_, i) => i !== index));
  };

  const handleSave = async () => {
    if (!title.trim()) return;

    setIsSaving(true);
    try {
      await onSave({
        title: title.trim(),
        description: description.trim() || undefined,
        agent: agent || undefined,
        todos: todos.map((t) => ({ text: t, completed: false })),
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card className="p-4 border-primary/50 bg-primary/5">
      <div className="space-y-4">
        {/* Title */}
        <div className="space-y-2">
          <Label htmlFor="step-title">Title *</Label>
          <Input
            id="step-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Step title..."
            className="bg-background"
          />
        </div>

        {/* Description */}
        <div className="space-y-2">
          <Label htmlFor="step-description">Description</Label>
          <Textarea
            id="step-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What should be done in this step..."
            rows={2}
            className="bg-background"
          />
        </div>

        {/* Agent */}
        <div className="space-y-2">
          <Label htmlFor="step-agent">Agent</Label>
          <Select value={agent} onValueChange={setAgent}>
            <SelectTrigger className="bg-background">
              <SelectValue placeholder="Select agent..." />
            </SelectTrigger>
            <SelectContent>
              {AGENTS.map((a) => (
                <SelectItem key={a.value} value={a.value}>
                  {a.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Todos */}
        <div className="space-y-2">
          <Label>Todos</Label>
          <div className="space-y-2">
            {todos.map((todo, i) => (
              <div key={i} className="flex items-center gap-2">
                <Input
                  value={todo}
                  onChange={(e) => {
                    const newTodos = [...todos];
                    newTodos[i] = e.target.value;
                    setTodos(newTodos);
                  }}
                  className="flex-1 bg-background"
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-destructive hover:text-destructive"
                  onClick={() => handleRemoveTodo(i)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            <div className="flex items-center gap-2">
              <Input
                value={newTodo}
                onChange={(e) => setNewTodo(e.target.value)}
                placeholder="Add a todo..."
                className="flex-1 bg-background"
                onKeyDown={(e) => e.key === "Enter" && handleAddTodo()}
              />
              <Button
                variant="outline"
                size="icon"
                className="h-8 w-8"
                onClick={handleAddTodo}
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-2 pt-2 border-t">
          <Button variant="ghost" size="sm" onClick={onCancel} disabled={isSaving}>
            <X className="h-4 w-4 mr-1" />
            Cancel
          </Button>
          <Button size="sm" onClick={handleSave} disabled={!title.trim() || isSaving}>
            <Save className="h-4 w-4 mr-1" />
            {isSaving ? "Saving..." : step ? "Update" : "Add Step"}
          </Button>
        </div>
      </div>
    </Card>
  );
}
