import type { Metadata } from "next";
import { Noto_Sans_KR, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Header } from "@/components/Header";
import { RadarBackground } from "@/components/RadarBackground";

const notoSansKR = Noto_Sans_KR({
  subsets: ["latin"],
  weight: ["400", "500", "900"],
  variable: "--font-noto-sans-kr",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "regime-rader",
  description: "국면 인식 기반 동적 자산배분 -- 정적 글라이드패스가 아닌 레짐 레이더.",
  icons: {
    icon: "/favicon_256.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body
        className={`${notoSansKR.variable} ${jetbrainsMono.variable} font-kr antialiased`}
      >
        <RadarBackground />
        <Header />
        <main className="mx-auto max-w-md px-4 pb-16 pt-4">{children}</main>
      </body>
    </html>
  );
}
