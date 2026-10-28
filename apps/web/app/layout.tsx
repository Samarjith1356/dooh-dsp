import type { ReactNode } from "react";
import { Providers } from "@/lib/providers";
import "./globals.css";
import "leaflet/dist/leaflet.css";

export const metadata = {
  title: "DOOH DSP Control Center",
  description: "UK & Ireland enterprise demand-side platform",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
