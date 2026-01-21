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
  // Prevent overscroll on iOS
  interactiveWidget: "resizes-content",
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
    startupImage: [
      // iPhone SE, iPod touch 7th gen
      {
        url: "/splash/apple-splash-640x1136.png",
        media:
          "(device-width: 320px) and (device-height: 568px) and (-webkit-device-pixel-ratio: 2)",
      },
      // iPhone 8, 7, 6s, 6
      {
        url: "/splash/apple-splash-750x1334.png",
        media:
          "(device-width: 375px) and (device-height: 667px) and (-webkit-device-pixel-ratio: 2)",
      },
      // iPhone 8 Plus, 7 Plus, 6s Plus, 6 Plus
      {
        url: "/splash/apple-splash-1242x2208.png",
        media:
          "(device-width: 414px) and (device-height: 736px) and (-webkit-device-pixel-ratio: 3)",
      },
      // iPhone X, XS, 11 Pro, 12 mini, 13 mini
      {
        url: "/splash/apple-splash-1125x2436.png",
        media:
          "(device-width: 375px) and (device-height: 812px) and (-webkit-device-pixel-ratio: 3)",
      },
      // iPhone XR, 11
      {
        url: "/splash/apple-splash-828x1792.png",
        media:
          "(device-width: 414px) and (device-height: 896px) and (-webkit-device-pixel-ratio: 2)",
      },
      // iPhone XS Max, 11 Pro Max
      {
        url: "/splash/apple-splash-1242x2688.png",
        media:
          "(device-width: 414px) and (device-height: 896px) and (-webkit-device-pixel-ratio: 3)",
      },
      // iPhone 12, 12 Pro, 13, 13 Pro, 14
      {
        url: "/splash/apple-splash-1170x2532.png",
        media:
          "(device-width: 390px) and (device-height: 844px) and (-webkit-device-pixel-ratio: 3)",
      },
      // iPhone 12 Pro Max, 13 Pro Max, 14 Plus
      {
        url: "/splash/apple-splash-1284x2778.png",
        media:
          "(device-width: 428px) and (device-height: 926px) and (-webkit-device-pixel-ratio: 3)",
      },
      // iPhone 14 Pro
      {
        url: "/splash/apple-splash-1179x2556.png",
        media:
          "(device-width: 393px) and (device-height: 852px) and (-webkit-device-pixel-ratio: 3)",
      },
      // iPhone 14 Pro Max, 15 Plus, 15 Pro Max
      {
        url: "/splash/apple-splash-1290x2796.png",
        media:
          "(device-width: 430px) and (device-height: 932px) and (-webkit-device-pixel-ratio: 3)",
      },
      // iPad mini, Air 9.7"
      {
        url: "/splash/apple-splash-1536x2048.png",
        media:
          "(device-width: 768px) and (device-height: 1024px) and (-webkit-device-pixel-ratio: 2)",
      },
      // iPad Pro 10.5"
      {
        url: "/splash/apple-splash-1668x2224.png",
        media:
          "(device-width: 834px) and (device-height: 1112px) and (-webkit-device-pixel-ratio: 2)",
      },
      // iPad Pro 11"
      {
        url: "/splash/apple-splash-1668x2388.png",
        media:
          "(device-width: 834px) and (device-height: 1194px) and (-webkit-device-pixel-ratio: 2)",
      },
      // iPad Pro 12.9"
      {
        url: "/splash/apple-splash-2048x2732.png",
        media:
          "(device-width: 1024px) and (device-height: 1366px) and (-webkit-device-pixel-ratio: 2)",
      },
    ],
  },
  formatDetection: {
    telephone: false,
    email: false,
    address: false,
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "/",
    siteName: "Wyld Fyre AI",
    title: "Wyld Fyre AI",
    description:
      "Multi-Agent AI Infrastructure powered by Claude. Talk to Wyld, your intelligent AI supervisor.",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Wyld Fyre AI",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Wyld Fyre AI",
    description:
      "Multi-Agent AI Infrastructure powered by Claude. Talk to Wyld, your intelligent AI supervisor.",
    images: ["/twitter-image.png"],
  },
  icons: {
    icon: [
      { url: "/icons/icon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/icons/icon-192x192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512x512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [
      { url: "/icons/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
    ],
    shortcut: "/favicon.ico",
    other: [
      {
        rel: "mask-icon",
        url: "/icons/safari-pinned-tab.svg",
        color: "#6b21a8",
      },
    ],
  },
  other: {
    // Android Chrome
    "mobile-web-app-capable": "yes",
    // Windows
    "msapplication-TileColor": "#1a1625",
    "msapplication-config": "/browserconfig.xml",
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
        {/* iOS-specific meta tags */}
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta
          name="apple-mobile-web-app-status-bar-style"
          content="black-translucent"
        />
        <meta name="apple-mobile-web-app-title" content="Wyld Fyre" />

        {/* iOS touch icon */}
        <link
          rel="apple-touch-icon"
          sizes="180x180"
          href="/icons/apple-touch-icon.png"
        />

        {/* Android Chrome theme */}
        <meta name="mobile-web-app-capable" content="yes" />

        {/* Disable iOS features that interfere with PWA */}
        <meta
          name="format-detection"
          content="telephone=no, date=no, email=no, address=no"
        />

        {/* Prevent pull-to-refresh on iOS and fix viewport width */}
        <style
          dangerouslySetInnerHTML={{
            __html: `
            html, body {
              width: 100%;
              max-width: 100vw;
              overflow-x: hidden;
              overscroll-behavior-y: contain;
              overscroll-behavior-x: none;
            }
            body {
              -webkit-overflow-scrolling: touch;
            }
            * {
              max-width: 100vw;
            }
          `,
          }}
        />
      </head>
      <body className={`${inter.className} antialiased w-screen max-w-[100vw] overflow-x-hidden`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
