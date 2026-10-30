"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useApi } from "@/lib/providers";
import { DemoBanner } from "@/components/demo-banner";

export default function IndexPage() {
  const { me, loading } = useApi();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!me) router.replace("/signup");
    else if (!me.profile) router.replace("/profile");
    else router.replace("/home");
  }, [me, loading, router]);

  return (
    <div className="min-h-screen">
      <DemoBanner />
      <p className="p-6 text-sm text-muted-foreground">Loading…</p>
    </div>
  );
}
