"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { DemoBanner } from "./demo-banner";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/home", label: "Home" },
  { href: "/campaigns/new", label: "New" },
  { href: "/wallet", label: "Wallet" },
  { href: "/assistant", label: "Assistant" },
];

export function AppShell({
  children,
  title,
  showNav = true,
}: {
  children: ReactNode;
  title?: string;
  showNav?: boolean;
}) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen flex-col">
      <DemoBanner />
      <header className="border-b border-border px-4 py-3">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-widest text-muted-foreground">Advertiser App</p>
            {title ? <h1 className="text-lg font-semibold">{title}</h1> : null}
          </div>
          {showNav ? (
            <nav className="flex flex-wrap gap-1" aria-label="Main">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "rounded-md px-2.5 py-1.5 text-sm",
                    pathname === item.href || pathname.startsWith(item.href + "/")
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          ) : null}
        </div>
      </header>
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-6">{children}</main>
    </div>
  );
}
