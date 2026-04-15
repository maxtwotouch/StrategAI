import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Civilization",
  description: "Play a strategy game against AI-led civilizations",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
