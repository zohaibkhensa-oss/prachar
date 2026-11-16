import type { Metadata } from "next";
import { Inter, Space_Grotesk, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { QueryProvider } from "@/lib/query";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://www.curvai.org"),
  title: "CURV AI — Your Entire Marketing Team. Powered by Intelligence.",
  description:
    "From strategy and creative production to social publishing and campaign growth, CURV AI brings your marketing workflow together in one intelligent platform.",
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  openGraph: {
    title: "CURV AI — Your Entire Marketing Team. Powered by Intelligence.",
    description:
      "From strategy and creative production to social publishing and campaign growth, CURV AI brings your marketing workflow together in one intelligent platform.",
    url: "https://www.curvai.org",
    siteName: "CURV AI",
    images: [
      {
        url: "/curv-logo.png",
        width: 800,
        height: 800,
        alt: "CURV AI",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "CURV AI — Your Entire Marketing Team. Powered by Intelligence.",
    description:
      "From strategy and creative production to social publishing and campaign growth, CURV AI brings your marketing workflow together in one intelligent platform.",
    images: ["/curv-logo.png"],
  },
  icons: {
    icon: "/curv-logo.png",
    apple: "/curv-logo.png",
  },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#08090D",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`dark ${inter.variable} ${spaceGrotesk.variable} ${plexMono.variable}`}>
      <body className="font-body bg-bg text-text antialiased min-h-screen">
        {/* Google Identity Services */}
        <script src="https://accounts.google.com/gsi/client" async defer />
        {/* Apple Sign-In JS */}
        <script src="https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js" async defer />
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
