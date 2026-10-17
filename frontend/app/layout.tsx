import type { Metadata, Viewport } from "next";
import "./globals.css";
import { amiri, cairo } from "./fonts";

export const metadata: Metadata = {
  title: "Beyond Style — صمّم قطعتك",
  description: "AI Arabic/English jewellery designer — Beyond Style UAE",
  applicationName: "Beyond Style",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, statusBarStyle: "default", title: "Beyond Style" },
  icons: {
    icon: [{ url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }],
    apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#FAF7F1",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Default is Arabic RTL; the page component switches document dir/lang
  // when the customer toggles language (true RTL layout, not text-align).
  return (
    <html lang="ar" dir="rtl" className={`${cairo.variable} ${amiri.variable}`}>
      <body>{children}</body>
    </html>
  );
}
