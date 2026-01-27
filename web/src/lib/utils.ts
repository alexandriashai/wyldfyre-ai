/**
 * Wyld Fyre AI - Utility Functions
 */

import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge class names with Tailwind CSS support
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a date for display
 */
export function formatDate(date: string | Date | undefined | null): string {
  if (!date) return '';
  const d = typeof date === 'string' ? new Date(date) : date;
  if (isNaN(d.getTime())) return '';
  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/**
 * Format a date with time for display
 */
export function formatDateTime(date: string | Date | undefined | null): string {
  if (!date) return '';
  const d = typeof date === 'string' ? new Date(date) : date;
  if (isNaN(d.getTime())) return '';
  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Format a relative time (e.g., "2 minutes ago")
 */
export function formatRelativeTime(date: string | Date | undefined | null): string {
  if (!date) return '';
  const d = typeof date === 'string' ? new Date(date) : date;
  if (isNaN(d.getTime())) return '';
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) {
    return 'just now';
  } else if (diffMinutes < 60) {
    return `${diffMinutes} minute${diffMinutes === 1 ? '' : 's'} ago`;
  } else if (diffHours < 24) {
    return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
  } else if (diffDays < 7) {
    return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
  } else {
    return formatDate(d);
  }
}

/**
 * Format duration in milliseconds to human readable string
 */
export function formatDuration(ms: number): string {
  if (ms < 1000) {
    return `${ms}ms`;
  } else if (ms < 60000) {
    return `${(ms / 1000).toFixed(1)}s`;
  } else if (ms < 3600000) {
    const minutes = Math.floor(ms / 60000);
    const seconds = Math.floor((ms % 60000) / 1000);
    return `${minutes}m ${seconds}s`;
  } else {
    const hours = Math.floor(ms / 3600000);
    const minutes = Math.floor((ms % 3600000) / 60000);
    return `${hours}h ${minutes}m`;
  }
}

/**
 * Truncate a string to a maximum length
 */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength - 3) + '...';
}

/**
 * Capitalize the first letter of a string
 */
export function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

/**
 * Generate a random ID
 */
export function generateId(): string {
  return Math.random().toString(36).substring(2) + Date.now().toString(36);
}

/**
 * Debounce a function
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout;
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

/**
 * Sleep for a specified number of milliseconds
 */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Agent status types
 */
export type AgentStatus = 'online' | 'busy' | 'offline' | 'error' | 'starting';

/**
 * Get status color class for text
 */
export function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    online: 'text-emerald-500',
    busy: 'text-amber-500',
    offline: 'text-gray-400',
    error: 'text-red-500',
    starting: 'text-blue-500',
  };
  return colors[status] || 'text-gray-400';
}

/**
 * Get status background color class
 */
export function getStatusBgColor(status: string): string {
  const colors: Record<string, string> = {
    online: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
    busy: 'bg-amber-500/10 text-amber-500 border-amber-500/20',
    offline: 'bg-gray-500/10 text-gray-400 border-gray-500/20',
    error: 'bg-red-500/10 text-red-500 border-red-500/20',
    starting: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
  };
  return colors[status] || 'bg-gray-500/10 text-gray-400 border-gray-500/20';
}

/**
 * Agent types
 */
export type AgentType = 'wyld' | 'code' | 'data' | 'infra' | 'research' | 'qa';

/**
 * Get agent-specific color class for text
 */
export function getAgentColor(agent: string): string {
  const colors: Record<string, string> = {
    wyld: 'text-purple-500',
    code: 'text-blue-500',
    data: 'text-emerald-500',
    infra: 'text-orange-500',
    research: 'text-cyan-500',
    qa: 'text-pink-500',
  };
  return colors[agent] || 'text-gray-500';
}

/**
 * Get agent-specific background color class
 */
export function getAgentBgColor(agent: string): string {
  const colors: Record<string, string> = {
    wyld: 'bg-purple-500/10 text-purple-500 border-purple-500/20',
    code: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
    data: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
    infra: 'bg-orange-500/10 text-orange-500 border-orange-500/20',
    research: 'bg-cyan-500/10 text-cyan-500 border-cyan-500/20',
    qa: 'bg-pink-500/10 text-pink-500 border-pink-500/20',
  };
  return colors[agent] || 'bg-gray-500/10 text-gray-500 border-gray-500/20';
}

/**
 * Get agent display name
 */
export function getAgentDisplayName(agent: AgentType): string {
  const names: Record<AgentType, string> = {
    wyld: 'Wyld',
    code: 'Code Agent',
    data: 'Data Agent',
    infra: 'Infra Agent',
    research: 'Research Agent',
    qa: 'QA Agent',
  };
  return names[agent] || capitalize(agent);
}

/**
 * Get agent icon name (for lucide-react)
 */
export function getAgentIcon(agent: AgentType): string {
  const icons: Record<AgentType, string> = {
    wyld: 'Flame',
    code: 'Code2',
    data: 'Database',
    infra: 'Server',
    research: 'Search',
    qa: 'ShieldCheck',
  };
  return icons[agent] || 'Bot';
}

/**
 * Copy text to clipboard
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Fallback for older browsers
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.opacity = '0';
    document.body.appendChild(textArea);
    textArea.select();
    try {
      document.execCommand('copy');
      return true;
    } catch {
      return false;
    } finally {
      document.body.removeChild(textArea);
    }
  }
}

/**
 * Check if code is running on client
 */
export function isClient(): boolean {
  return typeof window !== 'undefined';
}

/**
 * Check if code is running on mobile device
 */
export function isMobile(): boolean {
  if (!isClient()) return false;
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
    navigator.userAgent
  );
}

/**
 * Check if app is installed as PWA
 */
export function isPWA(): boolean {
  if (!isClient()) return false;
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    (window.navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

/**
 * Format file size
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

/**
 * Parse JSON safely
 */
export function safeJsonParse<T>(json: string, fallback: T): T {
  try {
    return JSON.parse(json);
  } catch {
    return fallback;
  }
}
