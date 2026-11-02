"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useApi } from "@/lib/providers";

export default function SignUpPage() {
  const { api, setMe } = useApi();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [accountType, setAccountType] = useState<"business" | "creator">("business");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!api) return;
    setBusy(true);
    setError("");
    try {
      const me = await api.signUp({ email, password, account_type: accountType });
      setMe(me);
      router.push("/profile");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign up");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell title="Sign up" showNav={false}>
      <Card>
        <CardHeader>
          <CardTitle>Create your account</CardTitle>
          <p className="text-sm text-muted-foreground">One email, then tell us about your business or creator brand.</p>
        </CardHeader>
        <CardContent>
          <form className="flex flex-col gap-4" onSubmit={onSubmit} data-testid="signup-form">
            <label className="flex flex-col gap-1 text-sm">
              Email
              <Input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                data-testid="signup-email"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Password
              <Input
                type="password"
                required
                minLength={6}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                data-testid="signup-password"
              />
            </label>
            <fieldset className="flex flex-col gap-2">
              <legend className="text-sm">I am a</legend>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant={accountType === "business" ? "default" : "outline"}
                  onClick={() => setAccountType("business")}
                  data-testid="account-business"
                >
                  Business
                </Button>
                <Button
                  type="button"
                  variant={accountType === "creator" ? "default" : "outline"}
                  onClick={() => setAccountType("creator")}
                  data-testid="account-creator"
                >
                  Creator
                </Button>
              </div>
            </fieldset>
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            <Button type="submit" disabled={busy || !api} data-testid="signup-submit">
              {busy ? "Creating…" : "Continue"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </AppShell>
  );
}
