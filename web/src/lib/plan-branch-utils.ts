/**
 * Plan Branch Utilities
 *
 * Smart branch integration for plans with automatic strategy detection.
 *
 * Rules:
 * 1. Protected branches (main, master, production) → Always create new branch
 * 2. Large plans (5+ steps) or risky changes → Auto-create branch
 * 3. Small fixes (1-3 steps, low risk) → Execute in place
 * 4. User explicitly requests isolation → Create branch
 */

import { PlanDetail, StepProgress } from "@/lib/api";

// Protected branch names that always require a new branch
export const PROTECTED_BRANCHES = [
  "main",
  "master",
  "production",
  "prod",
  "release",
  "staging",
];

// File patterns that indicate higher risk changes
const HIGH_RISK_PATTERNS = [
  /^\.env/,                    // Environment files
  /package\.json$/,            // Package dependencies
  /requirements\.txt$/,        // Python dependencies
  /docker/i,                   // Docker configuration
  /\.ya?ml$/,                  // YAML config files
  /config\//,                  // Config directories
  /migrations?\//,             // Database migrations
  /schema\./,                  // Schema files
  /auth/i,                     // Authentication related
  /security/i,                 // Security related
];

export type BranchStrategy = "current" | "new-branch";

export interface BranchStrategyResult {
  strategy: BranchStrategy;
  reason: string;
  suggestedBranchName?: string;
  isProtectedBranch: boolean;
  riskLevel: "low" | "medium" | "high";
}

export interface BranchConfig {
  prefix: string;
  protectedBranches: string[];
  riskThresholdSteps: number;
  autoCreateForProtected: boolean;
}

export const DEFAULT_BRANCH_CONFIG: BranchConfig = {
  prefix: "plan/",
  protectedBranches: PROTECTED_BRANCHES,
  riskThresholdSteps: 5,
  autoCreateForProtected: true,
};

/**
 * Check if a branch is protected
 */
export function isProtectedBranch(
  branchName: string,
  config: BranchConfig = DEFAULT_BRANCH_CONFIG
): boolean {
  const normalized = branchName.toLowerCase().trim();
  return config.protectedBranches.some(
    (protected_) => normalized === protected_.toLowerCase()
  );
}

/**
 * Assess the risk level of a plan based on its steps and files
 */
export function assessPlanRisk(plan: PlanDetail): "low" | "medium" | "high" {
  const steps = plan.steps || [];
  const filesExplored = plan.files_explored || [];

  // High risk indicators
  let riskScore = 0;

  // Number of steps
  if (steps.length >= 8) {
    riskScore += 3;
  } else if (steps.length >= 5) {
    riskScore += 2;
  } else if (steps.length >= 3) {
    riskScore += 1;
  }

  // Check for high-risk file patterns
  const highRiskFiles = filesExplored.filter((file) =>
    HIGH_RISK_PATTERNS.some((pattern) => pattern.test(file))
  );
  if (highRiskFiles.length > 3) {
    riskScore += 3;
  } else if (highRiskFiles.length > 0) {
    riskScore += 2;
  }

  // Check step descriptions for risky keywords
  const riskyKeywords = ["delete", "remove", "drop", "migrate", "deploy", "rollback"];
  const hasRiskySteps = steps.some((step) =>
    riskyKeywords.some((keyword) =>
      step.title.toLowerCase().includes(keyword) ||
      (step.description && step.description.toLowerCase().includes(keyword))
    )
  );
  if (hasRiskySteps) {
    riskScore += 2;
  }

  // Determine risk level
  if (riskScore >= 5) return "high";
  if (riskScore >= 3) return "medium";
  return "low";
}

/**
 * Determine the recommended branch strategy for a plan
 */
export function determineBranchStrategy(
  plan: PlanDetail,
  currentBranch: string,
  config: BranchConfig = DEFAULT_BRANCH_CONFIG
): BranchStrategyResult {
  const isProtected = isProtectedBranch(currentBranch, config);
  const riskLevel = assessPlanRisk(plan);
  const stepCount = plan.steps?.length || 0;

  // Rule 1: Protected branches always require new branch
  if (isProtected && config.autoCreateForProtected) {
    return {
      strategy: "new-branch",
      reason: `Branch '${currentBranch}' is protected. Changes will be made on a new branch.`,
      suggestedBranchName: generateBranchName(plan, config),
      isProtectedBranch: true,
      riskLevel,
    };
  }

  // Rule 2: High risk plans get new branch
  if (riskLevel === "high") {
    return {
      strategy: "new-branch",
      reason: "This plan involves significant changes. A new branch is recommended for safety.",
      suggestedBranchName: generateBranchName(plan, config),
      isProtectedBranch: false,
      riskLevel,
    };
  }

  // Rule 3: Large plans (5+ steps) get new branch
  if (stepCount >= config.riskThresholdSteps) {
    return {
      strategy: "new-branch",
      reason: `Plan has ${stepCount} steps. A new branch is recommended for easier review.`,
      suggestedBranchName: generateBranchName(plan, config),
      isProtectedBranch: false,
      riskLevel,
    };
  }

  // Rule 4: Small, low-risk plans execute in place
  return {
    strategy: "current",
    reason: "Small, low-risk plan. Changes will be made on the current branch.",
    isProtectedBranch: false,
    riskLevel,
  };
}

/**
 * Generate a branch name for a plan
 */
export function generateBranchName(
  plan: PlanDetail,
  config: BranchConfig = DEFAULT_BRANCH_CONFIG
): string {
  // Sanitize plan title for branch name
  const sanitizedTitle = plan.title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")    // Replace non-alphanumeric with hyphens
    .replace(/^-+|-+$/g, "")         // Remove leading/trailing hyphens
    .slice(0, 40);                   // Limit length

  // Add short ID for uniqueness
  const shortId = plan.id.slice(0, 8);

  return `${config.prefix}${sanitizedTitle}-${shortId}`;
}

/**
 * Format branch strategy for display
 */
export function formatBranchStrategy(result: BranchStrategyResult): {
  badge: string;
  badgeVariant: "default" | "secondary" | "destructive" | "outline";
  description: string;
} {
  if (result.strategy === "new-branch") {
    return {
      badge: result.isProtectedBranch ? "Protected" : "New Branch",
      badgeVariant: result.isProtectedBranch ? "destructive" : "default",
      description: result.reason,
    };
  }

  return {
    badge: "Current Branch",
    badgeVariant: "secondary",
    description: result.reason,
  };
}

/**
 * Get risk level badge styling
 */
export function getRiskBadgeStyle(riskLevel: "low" | "medium" | "high"): {
  variant: "default" | "secondary" | "destructive" | "outline";
  className: string;
} {
  switch (riskLevel) {
    case "high":
      return {
        variant: "destructive",
        className: "bg-red-500/10 text-red-600 border-red-500/30",
      };
    case "medium":
      return {
        variant: "outline",
        className: "bg-orange-500/10 text-orange-600 border-orange-500/30",
      };
    case "low":
    default:
      return {
        variant: "outline",
        className: "bg-green-500/10 text-green-600 border-green-500/30",
      };
  }
}
