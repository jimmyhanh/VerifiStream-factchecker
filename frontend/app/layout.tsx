import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "VerifiStream | Evidence workspace",
  description:
    "Inspect video claims, sources, and the evidence behind each assessment.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
