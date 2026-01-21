"use client";

import { Component, ReactNode } from "react";

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
  errorInfo?: React.ErrorInfo;
}

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

/**
 * Error boundary to catch and handle React component errors.
 *
 * Prevents entire app crashes from component-level errors.
 * Shows a fallback UI and allows retry.
 */
export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    // Log error details
    console.error("ErrorBoundary caught an error:", error, errorInfo);

    // Store error info for display
    this.setState({ errorInfo });

    // Call optional error callback
    this.props.onError?.(error, errorInfo);
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: undefined, errorInfo: undefined });
  };

  handleReload = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    if (this.state.hasError) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default error UI
      return (
        <ErrorFallback
          error={this.state.error}
          errorInfo={this.state.errorInfo}
          onRetry={this.handleRetry}
          onReload={this.handleReload}
        />
      );
    }

    return this.props.children;
  }
}

interface ErrorFallbackProps {
  error?: Error;
  errorInfo?: React.ErrorInfo;
  onRetry: () => void;
  onReload: () => void;
}

/**
 * Fallback UI shown when an error occurs.
 */
function ErrorFallback({
  error,
  errorInfo,
  onRetry,
  onReload,
}: ErrorFallbackProps) {
  const isDev = process.env.NODE_ENV === "development";

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-purple-950 to-slate-950 p-4">
      <div className="max-w-lg w-full bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-purple-500/20 p-8 shadow-xl">
        {/* Icon */}
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center">
            <svg
              className="w-8 h-8 text-red-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
        </div>

        {/* Title */}
        <h2 className="text-2xl font-bold text-center text-white mb-2">
          Something went wrong
        </h2>

        {/* Subtitle */}
        <p className="text-center text-gray-400 mb-6">
          An unexpected error occurred. You can try again or reload the page.
        </p>

        {/* Error details (dev only) */}
        {isDev && error && (
          <div className="mb-6 p-4 bg-red-500/10 rounded-lg border border-red-500/20">
            <p className="text-sm font-mono text-red-400 break-all">
              {error.name}: {error.message}
            </p>
            {errorInfo?.componentStack && (
              <details className="mt-2">
                <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-400">
                  Component Stack
                </summary>
                <pre className="mt-2 text-xs text-gray-500 overflow-auto max-h-40">
                  {errorInfo.componentStack}
                </pre>
              </details>
            )}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex gap-3">
          <button
            onClick={onRetry}
            className="flex-1 px-4 py-3 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-medium transition-colors"
          >
            Try Again
          </button>
          <button
            onClick={onReload}
            className="flex-1 px-4 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition-colors"
          >
            Reload Page
          </button>
        </div>

        {/* Support link */}
        <p className="text-center text-xs text-gray-500 mt-6">
          If the problem persists, please contact support.
        </p>
      </div>
    </div>
  );
}

/**
 * Minimal error boundary for individual components.
 * Shows a simple inline error message instead of full-screen UI.
 */
export function ComponentErrorBoundary({
  children,
  componentName = "Component",
}: {
  children: ReactNode;
  componentName?: string;
}) {
  return (
    <ErrorBoundary
      fallback={
        <div className="p-4 bg-red-500/10 rounded-lg border border-red-500/20">
          <p className="text-sm text-red-400">
            Error loading {componentName}. Please refresh the page.
          </p>
        </div>
      }
    >
      {children}
    </ErrorBoundary>
  );
}
