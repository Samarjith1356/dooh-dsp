"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { CATEGORIES } from "@/lib/api";
import { useApi } from "@/lib/providers";

const DEFAULT_LAT = 53.3498;
const DEFAULT_LNG = -6.2603;

export default function ProfilePage() {
  const { api, me, setMe, loading } = useApi();
  const router = useRouter();
  const [name, setName] = useState("");
  const [address, setAddress] = useState("1 Grafton Street, Dublin");
  const [category, setCategory] = useState("cafe");
  const [lat, setLat] = useState(DEFAULT_LAT);
  const [lng, setLng] = useState(DEFAULT_LNG);
  const [refusal, setRefusal] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && !me) router.replace("/signup");
  }, [loading, me, router]);

  useEffect(() => {
    if (!api) return;
    if (api.isCategoryRefused(category)) {
      setRefusal(api.categoryRefusalMessage(category));
    } else {
      setRefusal("");
    }
  }, [api, category]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!api) return;
    if (api.isCategoryRefused(category)) {
      setRefusal(api.categoryRefusalMessage(category));
      return;
    }
    setBusy(true);
    setError("");
    try {
      const updated = await api.updateProfile({ name, category, lat, lng, address });
      setMe(updated);
      router.push("/home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save profile");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell title="About you" showNav={false}>
      <Card>
        <CardHeader>
          <CardTitle>Your business</CardTitle>
          <p className="text-sm text-muted-foreground">We use this to find nearby screens and check compliance.</p>
        </CardHeader>
        <CardContent>
          <form className="flex flex-col gap-4" onSubmit={onSubmit} data-testid="profile-form">
            <label className="flex flex-col gap-1 text-sm">
              Business or brand name
              <Input required value={name} onChange={(e) => setName(e.target.value)} data-testid="profile-name" />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Address
              <Input required value={address} onChange={(e) => setAddress(e.target.value)} data-testid="profile-address" />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="flex flex-col gap-1 text-sm">
                Latitude
                <Input
                  type="number"
                  step="any"
                  required
                  value={lat}
                  onChange={(e) => setLat(Number(e.target.value))}
                  data-testid="profile-lat"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                Longitude
                <Input
                  type="number"
                  step="any"
                  required
                  value={lng}
                  onChange={(e) => setLng(Number(e.target.value))}
                  data-testid="profile-lng"
                />
              </label>
            </div>
            <label className="flex flex-col gap-1 text-sm">
              Category
              <select
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                data-testid="profile-category"
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            {refusal ? (
              <div
                role="alert"
                data-testid="category-refusal"
                className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm"
              >
                {refusal}
                <p className="mt-2 text-muted-foreground">You can&apos;t create a campaign with this category.</p>
              </div>
            ) : null}
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            <Button type="submit" disabled={busy || !!refusal || !api} data-testid="profile-submit">
              {busy ? "Saving…" : "Save and continue"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </AppShell>
  );
}
