"use client";

import { useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  FileQuestion,
  CheckCircle,
  SkipForward,
  Send,
  Loader2,
} from "lucide-react";

// Types for plan questions
export interface QuestionOption {
  value: string;
  label: string;
  description?: string;
}

export interface PlanQuestion {
  id: string;
  question: string;
  type: "single" | "multiple" | "text" | "hybrid";
  options?: QuestionOption[];
  placeholder?: string;
  required?: boolean;
}

export interface PlanQuestionsProps {
  questions: PlanQuestion[];
  onSubmit: (answers: Record<string, string | string[]>) => void;
  onSkip?: () => void;
  isSubmitting?: boolean;
  className?: string;
}

interface SingleQuestionProps {
  question: PlanQuestion;
  value: string;
  onChange: (value: string) => void;
}

function SingleQuestion({ question, value, onChange }: SingleQuestionProps) {
  const [otherValue, setOtherValue] = useState("");
  const isOther = value === "__other__";

  return (
    <RadioGroup
      value={value}
      onValueChange={(v: string) => {
        if (v !== "__other__") {
          setOtherValue("");
        }
        onChange(v);
      }}
      className="space-y-2"
    >
      {question.options?.map((option) => (
        <div
          key={option.value}
          className={cn(
            "flex items-start gap-3 p-3 rounded-lg border transition-colors cursor-pointer",
            value === option.value
              ? "border-primary bg-primary/5"
              : "border-border hover:border-primary/50"
          )}
          onClick={() => onChange(option.value)}
        >
          <RadioGroupItem value={option.value} id={option.value} className="mt-0.5" />
          <div className="flex-1 min-w-0">
            <Label htmlFor={option.value} className="font-medium cursor-pointer">
              {option.label}
            </Label>
            {option.description && (
              <p className="text-xs text-muted-foreground mt-0.5">
                {option.description}
              </p>
            )}
          </div>
        </div>
      ))}

      {/* Other option */}
      <div
        className={cn(
          "flex items-start gap-3 p-3 rounded-lg border transition-colors",
          isOther
            ? "border-primary bg-primary/5"
            : "border-border hover:border-primary/50"
        )}
      >
        <RadioGroupItem value="__other__" id="__other__" className="mt-0.5" />
        <div className="flex-1 min-w-0">
          <Label htmlFor="__other__" className="font-medium cursor-pointer">
            Other
          </Label>
          {isOther && (
            <Input
              value={otherValue}
              onChange={(e) => {
                setOtherValue(e.target.value);
                onChange(`__other__:${e.target.value}`);
              }}
              placeholder={question.placeholder || "Specify..."}
              className="mt-2 h-8"
              autoFocus
            />
          )}
        </div>
      </div>
    </RadioGroup>
  );
}

interface MultipleQuestionProps {
  question: PlanQuestion;
  value: string[];
  onChange: (value: string[]) => void;
}

function MultipleQuestion({ question, value, onChange }: MultipleQuestionProps) {
  const handleToggle = (optionValue: string) => {
    if (value.includes(optionValue)) {
      onChange(value.filter((v) => v !== optionValue));
    } else {
      onChange([...value, optionValue]);
    }
  };

  return (
    <div className="space-y-2">
      {question.options?.map((option) => (
        <div
          key={option.value}
          className={cn(
            "flex items-start gap-3 p-3 rounded-lg border transition-colors cursor-pointer",
            value.includes(option.value)
              ? "border-primary bg-primary/5"
              : "border-border hover:border-primary/50"
          )}
          onClick={() => handleToggle(option.value)}
        >
          <Checkbox
            checked={value.includes(option.value)}
            onCheckedChange={() => handleToggle(option.value)}
            className="mt-0.5"
          />
          <div className="flex-1 min-w-0">
            <Label className="font-medium cursor-pointer">
              {option.label}
            </Label>
            {option.description && (
              <p className="text-xs text-muted-foreground mt-0.5">
                {option.description}
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

interface TextQuestionProps {
  question: PlanQuestion;
  value: string;
  onChange: (value: string) => void;
}

function TextQuestion({ question, value, onChange }: TextQuestionProps) {
  return (
    <Textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={question.placeholder || "Enter your response..."}
      rows={3}
      className="resize-none"
    />
  );
}

interface HybridQuestionProps {
  question: PlanQuestion;
  value: { selected: string; custom: string };
  onChange: (value: { selected: string; custom: string }) => void;
}

function HybridQuestion({ question, value, onChange }: HybridQuestionProps) {
  return (
    <div className="space-y-3">
      <RadioGroup
        value={value.selected}
        onValueChange={(v: string) => onChange({ ...value, selected: v })}
        className="space-y-2"
      >
        {question.options?.map((option) => (
          <div
            key={option.value}
            className={cn(
              "flex items-start gap-3 p-3 rounded-lg border transition-colors cursor-pointer",
              value.selected === option.value
                ? "border-primary bg-primary/5"
                : "border-border hover:border-primary/50"
            )}
            onClick={() => onChange({ ...value, selected: option.value })}
          >
            <RadioGroupItem value={option.value} id={option.value} className="mt-0.5" />
            <div className="flex-1 min-w-0">
              <Label htmlFor={option.value} className="font-medium cursor-pointer">
                {option.label}
              </Label>
              {option.description && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  {option.description}
                </p>
              )}
            </div>
          </div>
        ))}
      </RadioGroup>

      {/* Custom input */}
      <div>
        <Label className="text-sm text-muted-foreground">
          Additional details (optional)
        </Label>
        <Input
          value={value.custom}
          onChange={(e) => onChange({ ...value, custom: e.target.value })}
          placeholder={question.placeholder || "Any additional context..."}
          className="mt-1.5"
        />
      </div>
    </div>
  );
}

export function PlanQuestions({
  questions,
  onSubmit,
  onSkip,
  isSubmitting,
  className,
}: PlanQuestionsProps) {
  // Initialize answers state
  const [answers, setAnswers] = useState<Record<string, string | string[] | { selected: string; custom: string }>>(() => {
    const initial: Record<string, string | string[] | { selected: string; custom: string }> = {};
    questions.forEach((q) => {
      if (q.type === "multiple") {
        initial[q.id] = [];
      } else if (q.type === "hybrid") {
        initial[q.id] = { selected: "", custom: "" };
      } else {
        initial[q.id] = "";
      }
    });
    return initial;
  });

  const handleSubmit = useCallback(() => {
    // Transform answers for submission
    const formattedAnswers: Record<string, string | string[]> = {};

    questions.forEach((q) => {
      const answer = answers[q.id];
      if (q.type === "hybrid" && typeof answer === "object" && !Array.isArray(answer)) {
        const hybrid = answer as { selected: string; custom: string };
        formattedAnswers[q.id] = hybrid.custom
          ? `${hybrid.selected}: ${hybrid.custom}`
          : hybrid.selected;
      } else if (typeof answer === "string" && answer.startsWith("__other__:")) {
        formattedAnswers[q.id] = answer.replace("__other__:", "");
      } else {
        formattedAnswers[q.id] = answer as string | string[];
      }
    });

    onSubmit(formattedAnswers);
  }, [answers, questions, onSubmit]);

  // Check if all required questions are answered
  const isValid = questions.every((q) => {
    if (!q.required) return true;
    const answer = answers[q.id];
    if (q.type === "multiple") {
      return Array.isArray(answer) && answer.length > 0;
    }
    if (q.type === "hybrid") {
      const hybrid = answer as { selected: string; custom: string };
      return hybrid.selected !== "";
    }
    return answer !== "" && answer !== "__other__";
  });

  return (
    <Card className={cn("border-primary/50 bg-primary/5", className)}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <FileQuestion className="h-5 w-5 text-primary" />
          Plan Refinement
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          Before I create the plan, I need a few clarifications:
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        {questions.map((question, index) => (
          <div key={question.id} className="space-y-3">
            <div className="flex items-start gap-2">
              <Badge variant="outline" className="h-5 w-5 shrink-0 flex items-center justify-center rounded-full text-xs">
                {index + 1}
              </Badge>
              <Label className="text-sm font-medium leading-relaxed">
                {question.question}
                {question.required && <span className="text-destructive ml-1">*</span>}
              </Label>
            </div>

            <div className="pl-7">
              {question.type === "single" && (
                <SingleQuestion
                  question={question}
                  value={answers[question.id] as string}
                  onChange={(v) => setAnswers({ ...answers, [question.id]: v })}
                />
              )}
              {question.type === "multiple" && (
                <MultipleQuestion
                  question={question}
                  value={answers[question.id] as string[]}
                  onChange={(v) => setAnswers({ ...answers, [question.id]: v })}
                />
              )}
              {question.type === "text" && (
                <TextQuestion
                  question={question}
                  value={answers[question.id] as string}
                  onChange={(v) => setAnswers({ ...answers, [question.id]: v })}
                />
              )}
              {question.type === "hybrid" && (
                <HybridQuestion
                  question={question}
                  value={answers[question.id] as { selected: string; custom: string }}
                  onChange={(v) => setAnswers({ ...answers, [question.id]: v })}
                />
              )}
            </div>
          </div>
        ))}

        {/* Actions */}
        <div className="flex items-center justify-between pt-4 border-t">
          {onSkip && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onSkip}
              disabled={isSubmitting}
            >
              <SkipForward className="h-4 w-4 mr-1.5" />
              Skip Questions
            </Button>
          )}
          <Button
            onClick={handleSubmit}
            disabled={!isValid || isSubmitting}
            className="ml-auto"
          >
            {isSubmitting ? (
              <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
            ) : (
              <Send className="h-4 w-4 mr-1.5" />
            )}
            Submit Answers
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
