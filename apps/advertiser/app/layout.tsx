import type { ReactNode } from "react";
import { Providers } from "@/lib/providers";
import "./globals.css";
import "leaflet/dist/leaflet.css";

export const metadata = {
  title: "Advertiser App",
  description: "Plan and launch outdoor screen campaigns in Dublin",
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
