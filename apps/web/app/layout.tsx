import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "DOOH DSP — UK & Ireland",
  description: "AI-planned campaigns, compiled rules, sub-millisecond bidding",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header>
          <h1>DOOH DSP · UK & Ireland</h1>
          <span className="muted">JCDecaux / VIOOH-shaped inventory · OpenRTB 2.6</span>
        </header>
        {children}
      </body>
    </html>
  );
}
