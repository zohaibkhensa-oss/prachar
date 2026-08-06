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
  title: "PRACHAR AI — Your Autonomous Marketing Team",
  description: "AI-driven premium advertising agency platform. One brand upload → organic + paid visibility across every major platform.",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#0a0a0f",
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
