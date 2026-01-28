/**
 * Media Protection System
 *
 * Protects images and media content from unauthorized downloads by:
 * - Disabling right-click context menus
 * - Preventing drag and drop
 * - Adding protective overlays and watermarks
 * - Implementing screenshot detection
 * - Canvas-based image obfuscation
 *
 * Usage:
 * import { initMediaProtection } from './media-protection';
 * initMediaProtection();
 */

/**
 * Media protection configuration
 */
interface MediaProtectionConfig {
  watermarkText: string;
  watermarkOpacity: number;
  protectionLevel: "basic" | "standard" | "aggressive";
  enableScreenshotDetection: boolean;
  enableCanvasProtection: boolean;
  excludeSelectors: string[];
}

/**
 * Default configuration
 */
const DEFAULT_CONFIG: MediaProtectionConfig = {
  watermarkText: "Protected Content",
  watermarkOpacity: 0.3,
  protectionLevel: "standard",
  enableScreenshotDetection: true,
  enableCanvasProtection: true,
  excludeSelectors: [".unprotected", '[data-protection="none"]'],
};

/**
 * Media Protection class
 */
export class MediaProtection {
  private config: MediaProtectionConfig;
  private observer: MutationObserver | null = null;
  private screenshotDetectionActive = false;
  private protectedElements = new WeakSet<Element>();

  constructor(config: Partial<MediaProtectionConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.init();
  }

  /**
   * Initialize media protection
   */
  private init(): void {
    this.injectStyles();
    this.setupEventListeners();
    this.protectExistingMedia();
    this.setupMutationObserver();

    if (this.config.enableScreenshotDetection) {
      this.setupScreenshotDetection();
    }
  }

  /**
   * Inject protection CSS styles
   */
  private injectStyles(): void {
    if (document.getElementById("media-protection-styles")) {
      return; // Already injected
    }

    const style = document.createElement("style");
    style.id = "media-protection-styles";
    style.textContent = `
      .media-protection-wrapper {
        position: relative;
        display: inline-block;
        overflow: hidden;
        -webkit-user-select: none;
        -moz-user-select: none;
        -ms-user-select: none;
        user-select: none;
        -webkit-touch-callout: none;
        -webkit-tap-highlight-color: transparent;
      }

      .media-protection-img,
      .media-protection-canvas {
        pointer-events: none;
        -webkit-user-drag: none;
        -moz-user-drag: none;
        -ms-user-drag: none;
        user-drag: none;
        display: block;
        max-width: 100%;
        height: auto;
      }

      .media-protection-overlay {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: transparent;
        pointer-events: auto;
        z-index: 1;
      }

      .media-protection-watermark {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%) rotate(-45deg);
        color: rgba(255, 255, 255, 0.7);
        font-size: 2rem;
        font-weight: bold;
        text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
        pointer-events: none;
        z-index: 2;
        white-space: nowrap;
        font-family: Arial, sans-serif;
      }

      .media-protection-flicker {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(255, 255, 255, 0.8);
        opacity: 0;
        pointer-events: none;
        z-index: 3;
        transition: opacity 0.1s ease;
      }

      .media-protection-toast {
        position: fixed;
        top: 20px;
        right: 20px;
        background: #dc3545;
        color: white;
        padding: 12px 20px;
        border-radius: 4px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        z-index: 10000;
        font-family: Arial, sans-serif;
        font-size: 14px;
        max-width: 300px;
        word-wrap: break-word;
        animation: slideIn 0.3s ease-out;
      }

      @keyframes slideIn {
        from {
          transform: translateX(100%);
          opacity: 0;
        }
        to {
          transform: translateX(0);
          opacity: 1;
        }
      }

      @keyframes flicker {
        0%, 100% { opacity: 0; }
        50% { opacity: 1; }
      }

      .media-protection-flicker.active {
        animation: flicker 0.1s ease-in-out;
      }
    `;

    document.head.appendChild(style);
  }

  /**
   * Set up global event listeners
   */
  private setupEventListeners(): void {
    // Disable right-click context menu on protected content
    document.addEventListener("contextmenu", this.handleContextMenu.bind(this));

    // Disable drag and drop
    document.addEventListener("dragstart", this.handleDragStart.bind(this));

    // Disable text selection on protected elements
    document.addEventListener("selectstart", this.handleSelectStart.bind(this));

    // Disable keyboard shortcuts
    document.addEventListener("keydown", this.handleKeyDown.bind(this));

    // Handle window focus/blur for screenshot detection
    window.addEventListener("blur", this.handleWindowBlur.bind(this));
    window.addEventListener("focus", this.handleWindowFocus.bind(this));
  }

  /**
   * Protect all existing media elements
   */
  private protectExistingMedia(): void {
    const mediaElements = document.querySelectorAll("img, video, canvas");
    mediaElements.forEach((element) => this.protectElement(element));
  }

  /**
   * Set up mutation observer to protect dynamically added media
   */
  private setupMutationObserver(): void {
    this.observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            const element = node as Element;

            // Check if the added element is media
            if (this.isMediaElement(element)) {
              this.protectElement(element);
            }

            // Check for media elements within the added element
            const mediaElements =
              element.querySelectorAll("img, video, canvas");
            mediaElements.forEach((mediaEl) => this.protectElement(mediaEl));
          }
        });
      });
    });

    this.observer.observe(document.body, {
      childList: true,
      subtree: true,
    });
  }

  /**
   * Check if element is a media element
   */
  private isMediaElement(element: Element): boolean {
    return ["IMG", "VIDEO", "CANVAS"].includes(element.tagName);
  }

  /**
   * Check if element should be excluded from protection
   */
  private isExcluded(element: Element): boolean {
    return this.config.excludeSelectors.some((selector) =>
      element.matches(selector),
    );
  }

  /**
   * Protect a single media element
   */
  private protectElement(element: Element): void {
    if (this.protectedElements.has(element) || this.isExcluded(element)) {
      return;
    }

    // Mark as protected
    this.protectedElements.add(element);

    // Apply protection based on element type
    if (element.tagName === "IMG") {
      this.protectImage(element as HTMLImageElement);
    } else if (element.tagName === "VIDEO") {
      this.protectVideo(element as HTMLVideoElement);
    } else if (element.tagName === "CANVAS") {
      this.protectCanvas(element as HTMLCanvasElement);
    }
  }

  /**
   * Protect image element
   */
  private protectImage(img: HTMLImageElement): void {
    if (img.closest(".media-protection-wrapper")) {
      return; // Already protected
    }

    // Create wrapper container
    const wrapper = document.createElement("div");
    wrapper.className = "media-protection-wrapper";

    // Insert wrapper before image
    img.parentNode?.insertBefore(wrapper, img);

    // Handle different image sources
    if (this.config.enableCanvasProtection && this.shouldUseCanvas(img)) {
      this.createCanvasProtection(img, wrapper);
    } else {
      // Simple protection without canvas
      img.classList.add("media-protection-img");
      wrapper.appendChild(img);
      this.addProtectionOverlay(wrapper);
    }

    this.addWatermark(wrapper);
    this.addFlickerOverlay(wrapper);
  }

  /**
   * Check if canvas protection should be used for image
   */
  private shouldUseCanvas(img: HTMLImageElement): boolean {
    const src = img.src.toLowerCase();
    // Use canvas for external images, avoid for data URLs and blob URLs
    return !src.startsWith("data:") && !src.startsWith("blob:");
  }

  /**
   * Create canvas-based protection for image
   */
  private createCanvasProtection(
    img: HTMLImageElement,
    wrapper: HTMLElement,
  ): void {
    const canvas = document.createElement("canvas");
    canvas.className = "media-protection-canvas";

    const waitForImageLoad = () => {
      if (img.complete && img.naturalWidth > 0) {
        this.renderImageToCanvas(img, canvas);
        wrapper.appendChild(canvas);
      } else {
        // Show image until canvas is ready
        img.classList.add("media-protection-img");
        wrapper.appendChild(img);

        img.addEventListener("load", () => {
          try {
            this.renderImageToCanvas(img, canvas);
            // Replace image with canvas
            if (wrapper.contains(img)) {
              wrapper.removeChild(img);
            }
            wrapper.appendChild(canvas);
          } catch (error) {
            // Fallback: just show image with protection
            console.warn("Canvas protection failed, using basic protection");
          }
        });

        img.addEventListener("error", () => {
          // Keep image with basic protection on load error
          console.warn("Image load failed, using basic protection");
        });
      }
    };

    waitForImageLoad();
    this.addProtectionOverlay(wrapper);
  }

  /**
   * Render image to canvas with obfuscation
   */
  private renderImageToCanvas(
    img: HTMLImageElement,
    canvas: HTMLCanvasElement,
  ): void {
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Set canvas dimensions
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    canvas.style.width = `${img.width || img.naturalWidth}px`;
    canvas.style.height = `${img.height || img.naturalHeight}px`;

    // Draw image
    ctx.drawImage(img, 0, 0);

    // Apply subtle noise for copy protection
    if (this.config.protectionLevel === "aggressive") {
      this.addCanvasNoise(ctx, canvas.width, canvas.height);
    }
  }

  /**
   * Add noise to canvas for copy protection
   */
  private addCanvasNoise(
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number,
  ): void {
    const imageData = ctx.getImageData(0, 0, width, height);
    const data = imageData.data;

    // Add minimal random noise
    for (let i = 0; i < data.length; i += 4) {
      const noise = (Math.random() - 0.5) * 2; // -1 to 1
      data[i] = Math.max(0, Math.min(255, data[i] + noise)); // Red
      data[i + 1] = Math.max(0, Math.min(255, data[i + 1] + noise)); // Green
      data[i + 2] = Math.max(0, Math.min(255, data[i + 2] + noise)); // Blue
    }

    ctx.putImageData(imageData, 0, 0);
  }

  /**
   * Protect video element
   */
  private protectVideo(video: HTMLVideoElement): void {
    video.setAttribute("controlslist", "nodownload");
    video.setAttribute("disablepictureinpicture", "true");
    video.style.pointerEvents = "none";

    // Wrap video similar to images
    if (!video.closest(".media-protection-wrapper")) {
      const wrapper = document.createElement("div");
      wrapper.className = "media-protection-wrapper";
      video.parentNode?.insertBefore(wrapper, video);
      wrapper.appendChild(video);

      this.addProtectionOverlay(wrapper);
      this.addWatermark(wrapper);
    }
  }

  /**
   * Protect canvas element
   */
  private protectCanvas(canvas: HTMLCanvasElement): void {
    // Override toDataURL and other methods
    const originalToDataURL = canvas.toDataURL;
    canvas.toDataURL = function () {
      console.warn("Canvas data extraction blocked");
      return "data:image/png;base64,";
    };

    canvas.style.pointerEvents = "none";
  }

  /**
   * Add transparent protection overlay
   */
  private addProtectionOverlay(wrapper: HTMLElement): void {
    const overlay = document.createElement("div");
    overlay.className = "media-protection-overlay";
    wrapper.appendChild(overlay);

    // Add interaction handlers
    overlay.addEventListener("contextmenu", (e) => e.preventDefault());
    overlay.addEventListener("dragstart", (e) => e.preventDefault());
    overlay.addEventListener("selectstart", (e) => e.preventDefault());
  }

  /**
   * Add watermark overlay
   */
  private addWatermark(wrapper: HTMLElement): void {
    const watermark = document.createElement("div");
    watermark.className = "media-protection-watermark";
    watermark.textContent = this.config.watermarkText;
    watermark.style.opacity = this.config.watermarkOpacity.toString();
    wrapper.appendChild(watermark);
  }

  /**
   * Add flicker overlay for screenshot detection
   */
  private addFlickerOverlay(wrapper: HTMLElement): void {
    const flickerOverlay = document.createElement("div");
    flickerOverlay.className = "media-protection-flicker";
    wrapper.appendChild(flickerOverlay);
  }

  /**
   * Handle right-click context menu
   */
  private handleContextMenu(e: Event): void {
    const target = e.target as Element;
    if (target.closest(".media-protection-wrapper")) {
      e.preventDefault();
      this.showProtectionNotice("Right-click disabled on protected content");
    }
  }

  /**
   * Handle drag start
   */
  private handleDragStart(e: Event): void {
    const target = e.target as Element;
    if (
      target.closest(".media-protection-wrapper") ||
      this.isMediaElement(target)
    ) {
      e.preventDefault();
      this.showProtectionNotice("Drag and drop disabled on protected content");
    }
  }

  /**
   * Handle text selection
   */
  private handleSelectStart(e: Event): void {
    const target = e.target as Element;
    if (target.closest(".media-protection-wrapper")) {
      e.preventDefault();
    }
  }

  /**
   * Handle keyboard shortcuts
   */
  private handleKeyDown(e: KeyboardEvent): void {
    // Block common screenshot/save shortcuts
    const blockedKeys = [
      "F12", // Developer tools
      "PrintScreen", // Screenshot
      "F2", // Rename
    ];

    const blockedCombos = [
      { ctrl: true, key: "s" }, // Save
      { ctrl: true, key: "a" }, // Select all (on protected content)
      { ctrl: true, key: "c" }, // Copy (on protected content)
      { ctrl: true, key: "u" }, // View source
      { ctrl: true, key: "i" }, // Developer tools
      { ctrl: true, shift: true, key: "i" }, // Developer tools
      { ctrl: true, shift: true, key: "c" }, // Inspector
      { ctrl: true, shift: true, key: "j" }, // Console
    ];

    if (blockedKeys.includes(e.key)) {
      e.preventDefault();
      this.showProtectionNotice(`${e.key} is disabled`);
      return;
    }

    for (const combo of blockedCombos) {
      if (
        e.ctrlKey === combo.ctrl &&
        e.shiftKey === !!combo.shift &&
        e.key.toLowerCase() === combo.key
      ) {
        const target = e.target as Element;
        if (
          target.closest(".media-protection-wrapper") ||
          combo.key === "u" ||
          combo.key === "i"
        ) {
          e.preventDefault();
          this.showProtectionNotice("Keyboard shortcut disabled");
          return;
        }
      }
    }
  }

  /**
   * Set up screenshot detection
   */
  private setupScreenshotDetection(): void {
    // Monitor for suspicious activity
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        this.triggerFlicker();
      }
    });

    // Monitor for print screen key (limited effectiveness)
    document.addEventListener("keyup", (e) => {
      if (e.key === "PrintScreen") {
        this.triggerFlicker();
        this.showProtectionNotice("Screenshot attempt detected");
      }
    });
  }

  /**
   * Handle window blur (potential screenshot)
   */
  private handleWindowBlur(): void {
    if (this.config.enableScreenshotDetection) {
      this.screenshotDetectionActive = true;
      this.triggerFlicker();
    }
  }

  /**
   * Handle window focus
   */
  private handleWindowFocus(): void {
    this.screenshotDetectionActive = false;
  }

  /**
   * Trigger flicker effect on all protected content
   */
  private triggerFlicker(): void {
    const flickerElements = document.querySelectorAll(
      ".media-protection-flicker",
    );
    flickerElements.forEach((element) => {
      const flickerEl = element as HTMLElement;
      flickerEl.style.opacity = "1";
      flickerEl.classList.add("active");

      setTimeout(() => {
        flickerEl.style.opacity = "0";
        flickerEl.classList.remove("active");
      }, 100);
    });
  }

  /**
   * Show protection notice to user
   */
  private showProtectionNotice(message: string): void {
    let toast = document.getElementById("media-protection-toast");

    if (!toast) {
      toast = document.createElement("div");
      toast.id = "media-protection-toast";
      toast.className = "media-protection-toast";
      document.body.appendChild(toast);
    }

    toast.textContent = message;
    toast.style.display = "block";

    setTimeout(() => {
      if (toast) {
        toast.style.display = "none";
      }
    }, 3000);
  }

  /**
   * Destroy the media protection instance
   */
  public destroy(): void {
    if (this.observer) {
      this.observer.disconnect();
      this.observer = null;
    }

    // Remove event listeners
    document.removeEventListener("contextmenu", this.handleContextMenu);
    document.removeEventListener("dragstart", this.handleDragStart);
    document.removeEventListener("selectstart", this.handleSelectStart);
    document.removeEventListener("keydown", this.handleKeyDown);
    window.removeEventListener("blur", this.handleWindowBlur);
    window.removeEventListener("focus", this.handleWindowFocus);

    // Remove injected styles
    const styles = document.getElementById("media-protection-styles");
    if (styles) {
      styles.remove();
    }
  }
}

// Global instance
let mediaProtectionInstance: MediaProtection | null = null;

/**
 * Initialize media protection with optional configuration
 */
export function initMediaProtection(
  config?: Partial<MediaProtectionConfig>,
): MediaProtection {
  if (mediaProtectionInstance) {
    mediaProtectionInstance.destroy();
  }

  mediaProtectionInstance = new MediaProtection(config);
  return mediaProtectionInstance;
}

/**
 * Get the current media protection instance
 */
export function getMediaProtection(): MediaProtection | null {
  return mediaProtectionInstance;
}

/**
 * Destroy media protection
 */
export function destroyMediaProtection(): void {
  if (mediaProtectionInstance) {
    mediaProtectionInstance.destroy();
    mediaProtectionInstance = null;
  }
}

// Auto-initialize if in browser environment
if (typeof window !== "undefined" && document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    initMediaProtection();
  });
} else if (typeof window !== "undefined") {
  initMediaProtection();
}
