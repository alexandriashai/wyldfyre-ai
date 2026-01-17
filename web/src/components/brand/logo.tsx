"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface LogoProps {
  className?: string;
  size?: "sm" | "md" | "lg" | "xl";
  showText?: boolean;
  animated?: boolean;
}

const sizes = {
  sm: "h-6 w-6",
  md: "h-8 w-8",
  lg: "h-12 w-12",
  xl: "h-16 w-16",
};

const textSizes = {
  sm: "text-lg",
  md: "text-xl",
  lg: "text-2xl",
  xl: "text-3xl",
};

export function Logo({
  className,
  size = "md",
  showText = true,
  animated = false,
}: LogoProps) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div
        className={cn(
          sizes[size],
          "relative",
          animated && "animate-pulse-glow"
        )}
      >
        <svg viewBox="0 0 512 512" className="h-full w-full">
          <defs>
            <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style={{ stopColor: "#1a1625" }} />
              <stop offset="100%" style={{ stopColor: "#2d1f47" }} />
            </linearGradient>
            <linearGradient id="faceGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style={{ stopColor: "#9333ea" }} />
              <stop offset="100%" style={{ stopColor: "#7c3aed" }} />
            </linearGradient>
            <linearGradient id="flameRed" x1="0%" y1="100%" x2="0%" y2="0%">
              <stop offset="0%" style={{ stopColor: "#dc2626" }} />
              <stop offset="100%" style={{ stopColor: "#ef4444" }} />
            </linearGradient>
            <linearGradient id="flameOrange" x1="0%" y1="100%" x2="0%" y2="0%">
              <stop offset="0%" style={{ stopColor: "#ea580c" }} />
              <stop offset="100%" style={{ stopColor: "#f97316" }} />
            </linearGradient>
            <linearGradient id="flameGold" x1="0%" y1="100%" x2="0%" y2="0%">
              <stop offset="0%" style={{ stopColor: "#f59e0b" }} />
              <stop offset="100%" style={{ stopColor: "#fbbf24" }} />
            </linearGradient>
            <linearGradient id="flameYellow" x1="0%" y1="100%" x2="0%" y2="0%">
              <stop offset="0%" style={{ stopColor: "#fbbf24" }} />
              <stop offset="100%" style={{ stopColor: "#fef3c7" }} />
            </linearGradient>
          </defs>
          <circle cx="256" cy="256" r="256" fill="url(#bgGrad)" />
          <path
            d="M340 450 C360 420 380 380 385 340 C390 300 385 260 375 220 C365 180 350 140 340 100 C335 75 335 55 340 35 C330 60 325 85 325 110 C325 150 335 190 340 230 C345 270 345 310 335 350 C325 390 310 420 340 450Z"
            fill="url(#flameRed)"
          />
          <path
            d="M300 450 C330 410 355 360 355 310 C355 260 340 210 320 160 C305 120 295 80 300 45 C285 80 280 115 285 155 C290 200 305 245 310 290 C315 340 305 390 300 450Z"
            fill="url(#flameOrange)"
          />
          <path
            d="M260 440 C295 400 315 350 310 295 C305 240 280 190 265 140 C255 105 255 70 265 40 C245 70 240 105 245 145 C250 190 270 240 275 290 C280 340 270 395 260 440Z"
            fill="url(#flameGold)"
          />
          <path
            d="M230 420 C260 380 275 330 270 280 C265 230 245 185 235 140 C228 110 230 80 240 55 C220 80 215 115 220 150 C225 190 240 235 245 280 C250 325 242 375 230 420Z"
            fill="url(#flameYellow)"
          />
          <path
            d="M215 460 C185 450 160 420 150 385 C140 350 145 315 155 285 L165 260 C155 250 150 235 152 220 C154 205 165 195 178 192 C170 178 170 162 178 150 C186 138 200 135 212 140 C208 125 215 110 230 105 C240 102 252 108 260 118 C275 100 290 95 305 105 C295 125 290 145 290 165 C290 190 280 210 265 225 C280 245 288 270 285 295 C282 325 265 350 245 370 C275 385 290 410 285 440 C280 465 255 480 225 475 C220 470 217 465 215 460Z"
            fill="url(#faceGrad)"
          />
          <path
            d="M195 195 Q210 182 230 185 Q245 188 250 198 Q235 208 215 206 Q198 204 195 195Z"
            fill="#fbbf24"
          />
        </svg>
      </div>
      {showText && (
        <span
          className={cn(
            textSizes[size],
            "font-bold tracking-tight brand-gradient-text"
          )}
        >
          Wyld Fyre
        </span>
      )}
    </div>
  );
}

// Icon-only version
export function LogoIcon({
  className,
  size = "md",
}: Omit<LogoProps, "showText">) {
  return <Logo className={className} size={size} showText={false} />;
}

// Animated flame icon for loading states
export function FlameLoader({ className }: { className?: string }) {
  return (
    <div className={cn("relative", className)}>
      <svg viewBox="0 0 64 64" className="h-full w-full animate-pulse">
        <defs>
          <linearGradient id="flameGradLoader" x1="0%" y1="100%" x2="0%" y2="0%">
            <stop offset="0%" style={{ stopColor: "#9333ea" }} />
            <stop offset="50%" style={{ stopColor: "#f97316" }} />
            <stop offset="100%" style={{ stopColor: "#fbbf24" }} />
          </linearGradient>
        </defs>
        <path
          d="M32 56 C20 56 12 46 12 34 C12 22 20 14 26 6 Q32 0 32 0 Q32 0 38 6 C44 14 52 22 52 34 C52 46 44 56 32 56Z"
          fill="url(#flameGradLoader)"
          className="animate-[flicker_1s_ease-in-out_infinite]"
        />
        <path
          d="M32 48 C24 48 20 42 20 34 C20 26 26 20 30 14 Q32 10 32 10 Q32 10 34 14 C38 20 44 26 44 34 C44 42 40 48 32 48Z"
          fill="#fef3c7"
          opacity="0.6"
        />
      </svg>
    </div>
  );
}
