/**
 * Lighthouse CI Configuration
 *
 * Performance Gate Configuration
 * Version: 1.0
 *
 * This configuration enforces performance budgets for the application.
 * All assertions must pass before deployment.
 */

module.exports = {
  ci: {
    collect: {
      // URLs to test
      url: [
        "http://localhost:8000/",
        "http://localhost:8000/providers",
        "http://localhost:8000/search",
        "http://localhost:8000/register",
        "http://localhost:8000/login",
      ],

      // Number of runs per URL for consistent results
      numberOfRuns: 3,

      // Server configuration
      startServerCommand: "php -S 127.0.0.1:8000 -t public",
      startServerReadyPattern: "Development Server",
      startServerReadyTimeout: 10000,

      // Device emulation settings
      settings: {
        preset: "desktop",

        // Network throttling to simulate realistic conditions
        throttling: {
          rttMs: 40,
          throughputKbps: 10240,
          requestLatencyMs: 0,
          downloadThroughputKbps: 0,
          uploadThroughputKbps: 0,
          cpuSlowdownMultiplier: 1,
        },

        // Storage reset configuration
        disableStorageReset: false,

        // Chrome flags for CI environment
        chromeFlags: "--no-sandbox --disable-gpu",
      },
    },

    assert: {
      // Use recommended Lighthouse assertion presets
      preset: "lighthouse:recommended",

      assertions: {
        // ============================================
        // CATEGORY SCORES (Lighthouse 0-100 scale)
        // ============================================

        "categories:performance": ["error", { minScore: 0.9 }],
        "categories:accessibility": ["error", { minScore: 0.95 }],
        "categories:best-practices": ["error", { minScore: 0.9 }],
        "categories:seo": ["error", { minScore: 0.9 }],

        // ============================================
        // CORE WEB VITALS (User Experience Metrics)
        // ============================================

        // First Contentful Paint - When first content appears
        "first-contentful-paint": ["error", { maxNumericValue: 1500 }],

        // Largest Contentful Paint - Main content loaded
        "largest-contentful-paint": ["error", { maxNumericValue: 2500 }],

        // Cumulative Layout Shift - Visual stability
        "cumulative-layout-shift": ["error", { maxNumericValue: 0.1 }],

        // Total Blocking Time - Interactivity measure
        "total-blocking-time": ["error", { maxNumericValue: 300 }],

        // Speed Index - Visual progress
        "speed-index": ["error", { maxNumericValue: 3400 }],

        // ============================================
        // RESOURCE SIZE BUDGETS (KB)
        // ============================================

        "resource-summary:script:size": ["error", { maxNumericValue: 153600 }], // 150KB JavaScript
        "resource-summary:stylesheet:size": [
          "error",
          { maxNumericValue: 51200 },
        ], // 50KB CSS
        "resource-summary:image:size": ["error", { maxNumericValue: 512000 }], // 500KB images
        "resource-summary:font:size": ["error", { maxNumericValue: 102400 }], // 100KB fonts
        "resource-summary:total:size": ["error", { maxNumericValue: 1024000 }], // 1MB total

        // ============================================
        // REQUEST COUNT BUDGETS
        // ============================================

        "resource-summary:script:count": ["error", { maxNumericValue: 10 }],
        "resource-summary:stylesheet:count": ["error", { maxNumericValue: 8 }],
        "resource-summary:image:count": ["error", { maxNumericValue: 20 }],
        "resource-summary:font:count": ["error", { maxNumericValue: 4 }],
        "resource-summary:total:count": ["error", { maxNumericValue: 50 }],

        // ============================================
        // ACCESSIBILITY REQUIREMENTS
        // ============================================

        "color-contrast": "error",
        "heading-order": "error",
        "image-alt": "error",
        "link-name": "error",
        "button-name": "error",
        "aria-required-attr": "error",

        // ============================================
        // BEST PRACTICES
        // ============================================

        "uses-https": "error",
        "is-on-https": "error",
        "no-vulnerable-libraries": "error",
        "external-anchors-use-rel-noopener": "error",

        // ============================================
        // SEO REQUIREMENTS
        // ============================================

        "document-title": "error",
        "meta-description": "error",
        "robots-txt": "error",
        hreflang: "off", // Not applicable for single-language site
        canonical: "error",

        // ============================================
        // PERFORMANCE OPTIMIZATIONS
        // ============================================

        "unused-css-rules": ["warn", { maxLength: 2048 }],
        "unused-javascript": ["warn", { maxLength: 20480 }],
        "modern-image-formats": "warn",
        "uses-optimized-images": "warn",
        "uses-webp-images": "warn",
        "efficient-animated-content": "error",
        "uses-responsive-images": "warn",

        // Font optimization
        "font-display": "error",
        "preload-fonts": "warn",

        // Network efficiency
        "uses-long-cache-ttl": "warn",
        "uses-rel-preconnect": "warn",
        "uses-text-compression": "error",
      },
    },

    upload: {
      // Upload results to temporary storage for CI
      target: "temporary-public-storage",
    },
  },
};
