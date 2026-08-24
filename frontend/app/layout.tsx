import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Beyond Style — صمّم قطعتك",
  description: "AI Arabic/English jewellery designer — Beyond Style UAE",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Default is Arabic RTL; the page component switches document dir/lang
  // when the customer toggles language (true RTL layout, not text-align).
  return (
    <html lang="ar" dir="rtl">
      <body>{children}</body>
    </html>
  );
}
