"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { BIDDING_EXPLAINER, type Wallet } from "@/lib/api";
import { useApi } from "@/lib/providers";
import { eurosToMicros, formatMicros } from "@/lib/utils";

export default function WalletPage() {
  const { api, me, loading } = useApi();
  const router = useRouter();
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [amount, setAmount] = useState(50);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const amountInvalid = !Number.isFinite(amount) || amount <= 0;

  useEffect(() => {
    if (loading) return;
    if (!me) router.replace("/signup");
  }, [loading, me, router]);

  useEffect(() => {
    if (!api) return;
    void api.getWallet().then(setWallet);
  }, [api]);

  async function topUp() {
    if (!api) return;
    if (amountInvalid) {
      setError("Top-up amount must be greater than zero.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      setWallet(await api.topUp({ micros: eurosToMicros(amount), currency: "EUR" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Top-up failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell title="Wallet">
      <div className="flex flex-col gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Balance</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold" data-testid="wallet-balance">
              {wallet ? formatMicros(wallet.balance.micros) : "—"}
            </p>
            <p className="text-xs text-muted-foreground">Demo balance — not real money</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Top up (demo)</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <label className="flex flex-col gap-1 text-sm">
              Amount (EUR)
              <Input
                type="number"
                min={1}
                value={amount}
                onChange={(e) => {
                  setAmount(Number(e.target.value));
                  setError("");
                }}
                data-testid="topup-amount"
              />
            </label>
            <Button
              type="button"
              onClick={() => void topUp()}
              disabled={busy || amountInvalid}
              data-testid="topup-submit"
            >
              {busy ? "Adding…" : "Add demo funds"}
            </Button>
            {error ? (
              <p role="alert" className="text-sm text-destructive" data-testid="topup-error">
                {error}
              </p>
            ) : null}
            <p className="text-sm text-muted-foreground">{BIDDING_EXPLAINER}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Invoices</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-2 text-sm" data-testid="invoice-list">
              {wallet?.invoices.map((inv) => (
                <li key={inv.id} className="flex items-center justify-between gap-2 border-b border-border py-2">
                  <span>
                    {inv.date} · {formatMicros(inv.amount.micros)}
                  </span>
                  <a className="text-primary underline-offset-2 hover:underline" href={inv.url}>
                    Demo PDF
                  </a>
                </li>
              ))}
              {!wallet?.invoices.length ? <li className="text-muted-foreground">No invoices yet.</li> : null}
            </ul>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
