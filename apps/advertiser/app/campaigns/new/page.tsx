"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  BIDDING_EXPLAINER,
  type ComplianceResult,
  type Daypart,
  type Estimate,
  type Screen,
} from "@/lib/api";
import { useApi } from "@/lib/providers";
import { eurosToMicros, formatMicros, formatNumber } from "@/lib/utils";

const ScreenMap = dynamic(() => import("@/components/blocks/screen-map").then((m) => m.ScreenMap), {
  ssr: false,
  loading: () => <div className="h-[280px] animate-pulse rounded-md bg-muted" />,
});

const STEPS = ["Goal", "Where", "When", "Budget", "Creative", "Review"] as const;
const DAYPARTS: { id: Daypart; label: string }[] = [
  { id: "morning", label: "Morning commute" },
  { id: "lunch", label: "Lunch" },
  { id: "evening", label: "Evening" },
  { id: "all_day", label: "All day" },
];

function readImageSize(file: File): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      resolve({ width: img.naturalWidth, height: img.naturalHeight });
      URL.revokeObjectURL(url);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Could not read image"));
    };
    img.src = url;
  });
}

function readVideoMeta(file: File): Promise<{ width: number; height: number; duration_s: number }> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";
    video.onloadedmetadata = () => {
      resolve({
        width: video.videoWidth,
        height: video.videoHeight,
        duration_s: Math.round(video.duration),
      });
      URL.revokeObjectURL(url);
    };
    video.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Could not read video"));
    };
    video.src = url;
  });
}

export default function NewCampaignPage() {
  const { api, me, loading } = useApi();
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [goal, setGoal] = useState("footfall");
  const [name, setName] = useState("");
  const [screens, setScreens] = useState<Screen[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [radius, setRadius] = useState(3000);
  const [start, setStart] = useState("2026-11-01");
  const [end, setEnd] = useState("2026-11-30");
  const [dayparts, setDayparts] = useState<Daypart[]>(["lunch"]);
  const [budgetEuros, setBudgetEuros] = useState(150);
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [creativeId, setCreativeId] = useState<string | undefined>();
  const [creativeMsg, setCreativeMsg] = useState("");
  const [creativeOk, setCreativeOk] = useState(false);
  const [demoVerdict, setDemoVerdict] = useState<ComplianceResult["verdict"]>("pass");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const center = useMemo(
    () => ({
      lat: me?.profile?.lat ?? 53.3498,
      lng: me?.profile?.lng ?? -6.2603,
    }),
    [me],
  );

  useEffect(() => {
    if (loading) return;
    if (!me) router.replace("/signup");
    else if (!me.profile) router.replace("/profile");
    else if (api?.isCategoryRefused(me.profile.category)) router.replace("/home");
  }, [api, loading, me, router]);

  useEffect(() => {
    if (!api || !me?.profile) return;
    void api.listScreens(center.lat, center.lng, radius).then((list) => {
      setScreens(list);
      setSelected((prev) => (prev.length ? prev.filter((id) => list.some((s) => s.id === id)) : list.slice(0, 3).map((s) => s.id)));
    });
  }, [api, me, center.lat, center.lng, radius]);

  useEffect(() => {
    if (!api || selected.length === 0) {
      setEstimate(null);
      return;
    }
    void api
      .estimate({
        screen_ids: selected,
        start,
        end,
        dayparts,
        budget: { micros: eurosToMicros(budgetEuros), currency: "EUR" },
      })
      .then(setEstimate);
  }, [api, selected, start, end, dayparts, budgetEuros]);

  function toggleDaypart(id: Daypart) {
    setDayparts((prev) => {
      if (id === "all_day") return ["all_day"];
      const next = prev.filter((d) => d !== "all_day");
      return next.includes(id) ? next.filter((d) => d !== id) : [...next, id];
    });
  }

  function toggleScreen(id: string) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  async function onCreativeFile(file: File | null) {
    if (!file || !api) return;
    setCreativeMsg("");
    setCreativeOk(false);
    setCreativeId(undefined);
    try {
      const isVideo = file.type.startsWith("video/");
      const meta = isVideo
        ? await readVideoMeta(file)
        : { ...(await readImageSize(file)), duration_s: undefined as number | undefined };
      const result = await api.uploadCreative({
        filename: file.name,
        mime: file.type || (isVideo ? "video/mp4" : "image/png"),
        width: meta.width,
        height: meta.height,
        duration_s: "duration_s" in meta ? meta.duration_s : undefined,
      });
      if (result.ok) {
        setCreativeId(result.creative_id);
        setCreativeOk(true);
        setCreativeMsg(`Accepted (${result.format?.replaceAll("_", " ")}). Demo upload only.`);
      } else {
        setCreativeMsg(result.problems.join(" "));
      }
    } catch (err) {
      setCreativeMsg(err instanceof Error ? err.message : "Upload failed");
    }
  }

  async function launch() {
    if (!api || !me?.profile) return;
    if (api.isCategoryRefused(me.profile.category)) {
      setError(api.categoryRefusalMessage(me.profile.category));
      return;
    }
    setBusy(true);
    setError("");
    try {
      const campaign = await api.createCampaign({
        name: name || `${goal} campaign`,
        goal,
        screen_ids: selected,
        start,
        end,
        dayparts,
        budget: { micros: eurosToMicros(budgetEuros), currency: "EUR" },
        creative_id: creativeId,
      });
      await api.submitCampaign(campaign.id, demoVerdict);
      router.push("/home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not launch");
    } finally {
      setBusy(false);
    }
  }

  const canNext =
    (step === 0 && !!goal) ||
    (step === 1 && selected.length > 0) ||
    (step === 2 && dayparts.length > 0 && !!start && !!end) ||
    (step === 3 && budgetEuros > 0) ||
    (step === 4 && creativeOk) ||
    step === 5;

  return (
    <AppShell title="New campaign">
      <div className="mb-4 flex flex-wrap gap-1" aria-label="Wizard steps">
        {STEPS.map((label, i) => (
          <span
            key={label}
            className={`rounded-md px-2 py-1 text-xs ${i === step ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}
          >
            {i + 1}. {label}
          </span>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{STEPS[step]}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {step === 0 ? (
            <fieldset className="flex flex-col gap-2" data-testid="step-goal">
              <legend className="sr-only">Goal</legend>
              {[
                { id: "footfall", label: "Footfall near me" },
                { id: "awareness", label: "Awareness in an area" },
                { id: "event", label: "An event date" },
              ].map((g) => (
                <Button
                  key={g.id}
                  type="button"
                  variant={goal === g.id ? "default" : "outline"}
                  className="justify-start"
                  onClick={() => {
                    setGoal(g.id);
                    if (!name) setName(g.label);
                  }}
                  data-testid={`goal-${g.id}`}
                >
                  {g.label}
                </Button>
              ))}
              <label className="flex flex-col gap-1 text-sm">
                Campaign name
                <Input value={name} onChange={(e) => setName(e.target.value)} data-testid="campaign-name" />
              </label>
            </fieldset>
          ) : null}

          {step === 1 ? (
            <div className="flex flex-col gap-3" data-testid="step-where">
              <label className="flex flex-col gap-1 text-sm">
                Radius (metres)
                <Input
                  type="number"
                  min={500}
                  max={15000}
                  value={radius}
                  onChange={(e) => setRadius(Number(e.target.value))}
                  data-testid="radius"
                />
              </label>
              <ScreenMap
                screens={screens}
                selectedIds={selected}
                center={center}
                onToggle={toggleScreen}
              />
              <ul className="max-h-40 overflow-y-auto text-sm">
                {screens.map((s) => (
                  <li key={s.id}>
                    <label className="flex cursor-pointer items-center gap-2 py-1">
                      <input
                        type="checkbox"
                        checked={selected.includes(s.id)}
                        onChange={() => toggleScreen(s.id)}
                        data-testid={`screen-${s.id}`}
                      />
                      <span>
                        {s.name} · {s.venue_type}
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
              <p className="text-xs text-muted-foreground">{selected.length} screens selected (demo inventory)</p>
            </div>
          ) : null}

          {step === 2 ? (
            <div className="flex flex-col gap-3" data-testid="step-when">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <label className="flex flex-col gap-1 text-sm">
                  Start
                  <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} data-testid="start-date" />
                </label>
                <label className="flex flex-col gap-1 text-sm">
                  End
                  <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} data-testid="end-date" />
                </label>
              </div>
              <div className="flex flex-wrap gap-2">
                {DAYPARTS.map((d) => (
                  <Button
                    key={d.id}
                    type="button"
                    size="sm"
                    variant={dayparts.includes(d.id) ? "default" : "outline"}
                    onClick={() => toggleDaypart(d.id)}
                    data-testid={`daypart-${d.id}`}
                  >
                    {d.label}
                  </Button>
                ))}
              </div>
            </div>
          ) : null}

          {step === 3 ? (
            <div className="flex flex-col gap-3" data-testid="step-budget">
              <label className="flex flex-col gap-1 text-sm">
                Total budget (EUR)
                <Input
                  type="number"
                  min={10}
                  step={10}
                  value={budgetEuros}
                  onChange={(e) => setBudgetEuros(Number(e.target.value))}
                  data-testid="budget-input"
                />
              </label>
              <div
                className="rounded-md border border-border bg-muted/40 p-3 text-sm"
                data-testid="estimate-range"
              >
                {estimate ? (
                  <>
                    <p>
                      Estimated plays:{" "}
                      <strong>
                        {formatNumber(estimate.plays_low)}–{formatNumber(estimate.plays_high)}
                      </strong>
                    </p>
                    <p>
                      Estimated impressions:{" "}
                      <strong>
                        {formatNumber(estimate.impressions_low)}–{formatNumber(estimate.impressions_high)}
                      </strong>
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">{estimate.note}</p>
                  </>
                ) : (
                  <p className="text-muted-foreground">Select screens to see a range estimate.</p>
                )}
              </div>
              <aside className="rounded-md border border-primary/30 bg-primary/5 p-3 text-sm" data-testid="bidding-explainer">
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">How bidding works</p>
                <p>{BIDDING_EXPLAINER}</p>
              </aside>
            </div>
          ) : null}

          {step === 4 ? (
            <div className="flex flex-col gap-3" data-testid="step-creative">
              <label className="flex flex-col gap-1 text-sm">
                Upload image or video
                <Input
                  type="file"
                  accept="image/png,image/jpeg,video/mp4,video/webm"
                  onChange={(e) => void onCreativeFile(e.target.files?.[0] ?? null)}
                  data-testid="creative-file"
                />
              </label>
              {creativeMsg ? (
                <p
                  className={`text-sm ${creativeOk ? "text-emerald-300" : "text-destructive"}`}
                  data-testid="creative-result"
                  role={creativeOk ? "status" : "alert"}
                >
                  {creativeMsg}
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">Need 1920×1080 or 1080×1920. Videos max 15 seconds.</p>
              )}
              <Button type="button" variant="outline" disabled data-testid="make-creative">
                Make one for me — coming soon
              </Button>
            </div>
          ) : null}

          {step === 5 ? (
            <div className="flex flex-col gap-3" data-testid="step-review">
              <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-muted-foreground">Name</dt>
                  <dd>{name || goal}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Budget</dt>
                  <dd>{formatMicros(eurosToMicros(budgetEuros))} (demo)</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Screens</dt>
                  <dd>{selected.length}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">When</dt>
                  <dd>
                    {start} → {end} · {dayparts.join(", ")}
                  </dd>
                </div>
              </dl>
              <label className="flex flex-col gap-1 text-sm">
                Demo compliance outcome
                <select
                  className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                  value={demoVerdict}
                  onChange={(e) => setDemoVerdict(e.target.value as ComplianceResult["verdict"])}
                  data-testid="demo-compliance"
                >
                  <option value="pass">Pass</option>
                  <option value="fix_needed">Fix needed</option>
                  <option value="human_review">Human review</option>
                </select>
              </label>
              <aside className="rounded-md border border-primary/30 bg-primary/5 p-3 text-sm">{BIDDING_EXPLAINER}</aside>
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
            </div>
          ) : null}

          <div className="flex flex-wrap justify-between gap-2 pt-2">
            <Button type="button" variant="outline" disabled={step === 0} onClick={() => setStep((s) => s - 1)}>
              Back
            </Button>
            {step < STEPS.length - 1 ? (
              <Button
                type="button"
                disabled={!canNext}
                onClick={() => setStep((s) => s + 1)}
                data-testid="wizard-next"
              >
                Next
              </Button>
            ) : (
              <Button type="button" disabled={busy || !creativeOk} onClick={() => void launch()} data-testid="wizard-launch">
                {busy ? "Launching…" : "Pay from wallet & launch"}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </AppShell>
  );
}
