import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"], display: "swap" });

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  userScalable: true,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#6b21a8" },
    { media: "(prefers-color-scheme: dark)", color: "#1a1625" },
  ],
  viewportFit: "cover",
};

export const metadata: Metadata = {
  title: {
    default: "Wyld Fyre AI",
    template: "%s | Wyld Fyre AI",
  },
  description:
    "Multi-Agent AI Infrastructure powered by Claude. Talk to Wyld, your intelligent AI supervisor.",
  keywords: [
    "AI",
    "multi-agent",
    "Claude",
    "infrastructure",
    "automation",
    "Wyld Fyre",
    "AI assistant",
  ],
  authors: [{ name: "Allie Eden" }],
  creator: "Allie Eden",
  publisher: "Wyld Fyre AI",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Wyld Fyre",
  },
  formatDetection: {
    telephone: false,
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "/",
    siteName: "Wyld Fyre AI",
    title: "Wyld Fyre AI",
    description:
      "Multi-Agent AI Infrastructure powered by Claude. Talk to Wyld, your intelligent AI supervisor.",
  },
  twitter: {
    card: "summary_large_image",
    title: "Wyld Fyre AI",
    description:
      "Multi-Agent AI Infrastructure powered by Claude. Talk to Wyld, your intelligent AI supervisor.",
  },
  icons: {
    icon: [
      { url: "/icons/icon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/icons/icon-192x192.png", sizes: "192x192", type: "image/png" },
    ],
    apple: [
      { url: "/icons/icon-180x180.png", sizes: "180x180", type: "image/png" },
    ],
    shortcut: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* PWA splash screens for iOS */}
        <link
          rel="apple-touch-startup-image"
          href="/splash/splash-640x1136.png"
          media="(device-width: 320px) and (device-height: 568px) and (-webkit-device-pixel-ratio: 2)"
        />
        <link
          rel="apple-touch-startup-image"
          href="/splash/splash-750x1334.png"
          media="(device-width: 375px) and (device-height: 667px) and (-webkit-device-pixel-ratio: 2)"
        />
        <link
          rel="apple-touch-startup-image"
          href="/splash/splash-1242x2208.png"
          media="(device-width: 414px) and (device-height: 736px) and (-webkit-device-pixel-ratio: 3)"
        />
        <link
          rel="apple-touch-startup-image"
          href="/splash/splash-1125x2436.png"
          media="(device-width: 375px) and (device-height: 812px) and (-webkit-device-pixel-ratio: 3)"
        />
        <link
          rel="apple-touch-startup-image"
          href="/splash/splash-1536x2048.png"
          media="(min-device-width: 768px) and (max-device-width: 1024px) and (-webkit-device-pixel-ratio: 2)"
        />
      </head>
      <body className={`${inter.className} antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
