/**
 * Review Code Manager Component - Provider Dashboard
 *
 * Manages review codes for providers, allowing them to:
 * - Generate new guest review codes
 * - List active codes with copy functionality
 * - View code usage statistics
 * - Revoke unused codes
 *
 * Usage:
 * <div x-data="reviewCodeManager()">
 *   <!-- Code management UI -->
 * </div>
 */

/**
 * Review code from API
 */
interface ReviewCode {
  id: number;
  code: string;
  created_at: string;
  expires_at: string;
  note: string | null;
}

/**
 * Code statistics
 */
interface CodeStats {
  active: number;
  used: number;
  expired: number;
  revoked: number;
  total: number;
  max_allowed: number;
}

/**
 * API response types
 */
interface ListCodesResponse {
  codes: ReviewCode[];
  stats: CodeStats;
}

interface GenerateCodeResponse {
  success: boolean;
  code?: string;
  expires_at?: string;
  error?: string;
}

interface RevokeCodeResponse {
  success: boolean;
  message?: string;
  error?: string;
}

/**
 * Review Code Manager Component Interface
 */
export interface ReviewCodeManagerComponent {
  // Component state
  codes: ReviewCode[];
  stats: CodeStats | null;
  isLoading: boolean;
  isGenerating: boolean;
  error: string | null;
  successMessage: string | null;
  copiedCodeId: number | null;

  // Form state
  showGenerateForm: boolean;
  newCodeNote: string;
  expiryDays: number;

  // Component methods
  init(): void;
  loadCodes(): Promise<void>;
  generateCode(): Promise<void>;
  revokeCode(code: string): Promise<void>;
  copyCode(code: ReviewCode): Promise<void>;
  shareCode(code: ReviewCode): Promise<void>;
  formatDate(dateStr: string): string;
  getDaysUntilExpiry(expiresAt: string): number;
  closeGenerateForm(): void;

  // Computed properties
  get canGenerateMore(): boolean;
  get activeCodesRemaining(): number;
  get hasActiveCodes(): boolean;
}

/**
 * Create Review Code Manager component
 */
export function createReviewCodeManager(): ReviewCodeManagerComponent {
  const component: ReviewCodeManagerComponent = {
    // Initial state
    codes: [],
    stats: null,
    isLoading: true,
    isGenerating: false,
    error: null,
    successMessage: null,
    copiedCodeId: null,

    // Form state
    showGenerateForm: false,
    newCodeNote: "",
    expiryDays: 30,

    /**
     * Initialize the component
     */
    init(): void {
      this.loadCodes();
    },

    /**
     * Load active codes and statistics from the API
     */
    async loadCodes(): Promise<void> {
      this.isLoading = true;
      this.error = null;

      try {
        const token = sessionStorage.getItem("access_token");
        const response = await fetch("/api/v1/provider/review-codes", {
          headers: {
            Authorization: `Bearer ${token}`,
            "X-Requested-With": "XMLHttpRequest",
          },
        });

        if (!response.ok) {
          throw new Error("Failed to load review codes");
        }

        const data: ListCodesResponse = await response.json();
        this.codes = data.codes;
        this.stats = data.stats;
      } catch (error) {
        this.error =
          error instanceof Error ? error.message : "Failed to load codes";
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * Generate a new review code
     */
    async generateCode(): Promise<void> {
      if (!this.canGenerateMore) {
        this.error = `Maximum ${
          this.stats?.max_allowed ?? 10
        } active codes allowed`;
        return;
      }

      this.isGenerating = true;
      this.error = null;
      this.successMessage = null;

      try {
        const token = sessionStorage.getItem("access_token");
        const response = await fetch("/api/v1/provider/review-codes", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
            "X-Requested-With": "XMLHttpRequest",
          },
          body: JSON.stringify({
            note: this.newCodeNote || null,
            expiry_days: this.expiryDays,
          }),
        });

        const data: GenerateCodeResponse = await response.json();

        if (!data.success) {
          throw new Error(data.error ?? "Failed to generate code");
        }

        // Reload codes to show the new one
        await this.loadCodes();

        this.successMessage = `Code ${data.code} generated successfully!`;
        this.showGenerateForm = false;
        this.newCodeNote = "";
        this.expiryDays = 30;

        // Clear success message after 5 seconds
        setTimeout(() => {
          this.successMessage = null;
        }, 5000);

        // Dispatch custom event for other components
        window.dispatchEvent(
          new CustomEvent("review-code:generated", {
            detail: { code: data.code },
          }),
        );
      } catch (error) {
        this.error =
          error instanceof Error ? error.message : "Failed to generate code";
      } finally {
        this.isGenerating = false;
      }
    },

    /**
     * Revoke an unused review code
     */
    async revokeCode(code: string): Promise<void> {
      if (!confirm("Are you sure you want to revoke this code?")) {
        return;
      }

      try {
        const token = sessionStorage.getItem("access_token");
        const response = await fetch(`/api/v1/provider/review-codes/${code}`, {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${token}`,
            "X-Requested-With": "XMLHttpRequest",
          },
        });

        const data: RevokeCodeResponse = await response.json();

        if (!data.success) {
          throw new Error(data.error ?? "Failed to revoke code");
        }

        // Reload codes to update the list
        await this.loadCodes();

        this.successMessage = data.message ?? "Code revoked successfully";

        // Clear success message after 3 seconds
        setTimeout(() => {
          this.successMessage = null;
        }, 3000);
      } catch (error) {
        this.error =
          error instanceof Error ? error.message : "Failed to revoke code";
      }
    },

    /**
     * Copy review code to clipboard
     */
    async copyCode(code: ReviewCode): Promise<void> {
      try {
        await navigator.clipboard.writeText(code.code);
        this.copiedCodeId = code.id;

        // Clear copied state after 2 seconds
        setTimeout(() => {
          this.copiedCodeId = null;
        }, 2000);
      } catch (error) {
        // Fallback for browsers without clipboard API
        const textArea = document.createElement("textarea");
        textArea.value = code.code;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand("copy");
        document.body.removeChild(textArea);

        this.copiedCodeId = code.id;
        setTimeout(() => {
          this.copiedCodeId = null;
        }, 2000);
      }
    },

    /**
     * Share review code via Web Share API or fallback
     */
    async shareCode(code: ReviewCode): Promise<void> {
      const shareUrl = `${window.location.origin}/review?code=${code.code}`;
      const shareText = `Use this code to leave a review: ${code.code}`;

      if (navigator.share) {
        try {
          await navigator.share({
            title: "Review Code",
            text: shareText,
            url: shareUrl,
          });
        } catch (error) {
          // User cancelled sharing
        }
      } else {
        // Fallback: copy URL to clipboard
        await navigator.clipboard.writeText(shareUrl);
        this.successMessage = "Review URL copied to clipboard";

        setTimeout(() => {
          this.successMessage = null;
        }, 3000);
      }
    },

    /**
     * Format date string for display
     */
    formatDate(dateStr: string): string {
      return new Date(dateStr).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    },

    /**
     * Calculate days until expiry
     */
    getDaysUntilExpiry(expiresAt: string): number {
      const expiry = new Date(expiresAt);
      const now = new Date();
      const diffTime = expiry.getTime() - now.getTime();
      return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    },

    /**
     * Close the generate form
     */
    closeGenerateForm(): void {
      this.showGenerateForm = false;
      this.newCodeNote = "";
      this.expiryDays = 30;
      this.error = null;
    },

    /**
     * Check if more codes can be generated
     */
    get canGenerateMore(): boolean {
      if (!this.stats) return false;
      return this.stats.active < this.stats.max_allowed;
    },

    /**
     * Get remaining active code slots
     */
    get activeCodesRemaining(): number {
      if (!this.stats) return 0;
      return Math.max(0, this.stats.max_allowed - this.stats.active);
    },

    /**
     * Check if there are active codes
     */
    get hasActiveCodes(): boolean {
      return this.codes.length > 0;
    },
  };

  return component;
}

/**
 * Alpine.js component factory
 */
export function reviewCodeManager(): ReviewCodeManagerComponent {
  return createReviewCodeManager();
}

// Export for global access
declare global {
  interface Window {
    reviewCodeManager: () => ReviewCodeManagerComponent;
  }
}

if (typeof window !== "undefined") {
  window.reviewCodeManager = reviewCodeManager;
}
