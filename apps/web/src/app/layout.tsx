import type { Metadata } from "next";
import "./globals.css";
import { QueryProvider } from "@/lib/query";

export const metadata: Metadata = {
  title: "CURV AI — AI Advertising Operating System",
  description:
    "The world's most advanced AI advertising platform. One brand upload. Autonomous weekly loops across every major platform worldwide.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="font-body bg-bg text-text antialiased min-h-screen">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
