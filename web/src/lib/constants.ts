export const CHAT_TAGS = {
  lifecycle: [
    { value: "planning", label: "Planning", color: "#3B82F6" },
    { value: "design", label: "Design", color: "#8B5CF6" },
    { value: "development", label: "Development", color: "#10B981" },
    { value: "content", label: "Content", color: "#F59E0B" },
    { value: "testing", label: "Testing", color: "#06B6D4" },
    { value: "deployment", label: "Deployment", color: "#EF4444" },
    { value: "maintenance", label: "Maintenance", color: "#6B7280" },
  ],
  system: [
    { value: "bug-fix", label: "Bug Fix", color: "#DC2626" },
    { value: "feature", label: "Feature", color: "#16A34A" },
    { value: "config", label: "Configuration", color: "#CA8A04" },
    { value: "infrastructure", label: "Infrastructure", color: "#9333EA" },
  ],
};

export const ALL_TAGS = [...CHAT_TAGS.lifecycle, ...CHAT_TAGS.system];

export function getTagInfo(value: string) {
  return ALL_TAGS.find((t) => t.value === value);
}
