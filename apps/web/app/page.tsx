"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Advertiser = { id: number; company: string; markets: string[] };
type Spec = { id: number; publisher: string; format_code: string; width: number; height: number; aspect: string; country: string };
type Creative = { id: number; filename: string; validation_status: string; asset_uri: string; width: number; height: number };
type Campaign = {
  id: number;
  name: string;
  state: string;
  advertiser_id: number;
  bid_cpm_micros: number;
  creative_ids: number[];
};
type Hourly = { hour: string; event_type: string; bids: number; imps: number; spend_micros: number };

export default function Page() {
  const [advertisers, setAdvertisers] = useState<Advertiser[]>([]);
  const [specs, setSpecs] = useState<Spec[]>([]);
  const [creatives, setCreatives] = useState<Creative[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [hourly, setHourly] = useState<Hourly[]>([]);
  const [insight, setInsight] = useState("");
  const [chat, setChat] = useState("Run a 2-week brand awareness campaign targeting commuters in Dublin");
  const [reply, setReply] = useState("");
  const [advId, setAdvId] = useState<number>(0);
  const [campId, setCampId] = useState<number>(0);
  const [specId, setSpecId] = useState<number>(0);
  const [geoIds, setGeoIds] = useState<number[]>([]);
  const [company, setCompany] = useState("Acme Outdoors");
  const [email, setEmail] = useState("buyer@acme.example");
  const [campName, setCampName] = useState("Dublin commute burst");
  const [status, setStatus] = useState("");

  async function refresh(id = advId) {
    const ads: Advertiser[] = await fetch(`${API}/v1/advertisers`).then((r) => r.json());
    setAdvertisers(ads);
    const specs: Spec[] = await fetch(`${API}/v1/screen-specs`).then((r) => r.json());
    setSpecs(specs);
    if (!id && ads[0]) id = ads[0].id;
    if (id) {
      setAdvId(id);
      const geos: { id: number }[] = await fetch(`${API}/v1/geofences?advertiser_id=${id}`).then((r) => r.json());
      setGeoIds(geos.map((g) => g.id));
      const cr: Creative[] = await fetch(`${API}/v1/creatives?advertiser_id=${id}`).then((r) => r.json());
      setCreatives(cr);
      const camps: Campaign[] = await fetch(`${API}/v1/campaigns?advertiser_id=${id}`).then((r) => r.json());
      setCampaigns(camps);
      if (camps[0] && !campId) setCampId(camps[0].id);
      const ins = await fetch(`${API}/v1/insights?advertiser_id=${id}`).then((r) => r.json());
      setInsight(ins.live || "");
      const hours: Hourly[] = await fetch(`${API}/v1/analytics/hourly?advertiser_id=${id}`).then((r) => r.json());
      setHourly(hours);
    }
    if (specs[0] && !specId) setSpecId(specs[0].id);
  }

  useEffect(() => {
    refresh().catch((e) => setStatus(String(e)));
    const t = setInterval(() => refresh().catch(() => undefined), 8000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedCamp = useMemo(() => campaigns.find((c) => c.id === campId), [campaigns, campId]);

  async function onSignup(e: FormEvent) {
    e.preventDefault();
    const res = await fetch(`${API}/v1/advertisers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company, email, name: "Buyer", markets: ["GB", "IE"] }),
    });
    const body = await res.json();
    setStatus(`Advertiser #${body.id}`);
    await refresh(body.id);
  }

  async function onUpload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    fd.set("advertiser_id", String(advId));
    fd.set("spec_id", String(specId));
    const res = await fetch(`${API}/v1/creatives`, { method: "POST", body: fd });
    const body = await res.json();
    setStatus(`Creative ${body.validation_status}`);
    await refresh(advId);
  }

  async function onCreateCampaign(e: FormEvent) {
    e.preventDefault();
    const valid = creatives.filter((c) => c.validation_status === "valid").map((c) => c.id);
    const res = await fetch(`${API}/v1/campaigns`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        advertiser_id: advId,
        name: campName,
        bid_cpm_micros: 6500000,
        total_cap_micros: 50000000,
        currency: "GBP",
        creative_ids: valid,
        geofence_ids: geoIds,
      }),
    });
    const body = await res.json();
    setCampId(body.id);
    setStatus(`Campaign #${body.id} draft`);
    await refresh(advId);
  }

  async function setState(state: string) {
    if (!campId) return;
    if (state === "active" && selectedCamp?.state === "draft") {
      await fetch(`${API}/v1/campaigns/${campId}/state`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ state: "pending_approval" }),
      });
    }
    const res = await fetch(`${API}/v1/campaigns/${campId}/state`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state }),
    });
    if (!res.ok) setStatus(await res.text());
    await refresh(advId);
  }

  async function onChat(e: FormEvent) {
    e.preventDefault();
    const res = await fetch(`${API}/v1/agent/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ advertiser_id: advId, campaign_id: campId || null, message: chat }),
    });
    const body = await res.json();
    setReply(body.reply);
    if (body.plan && campId) {
      await fetch(`${API}/v1/campaigns/${campId}/plans`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...body.plan, approved: false }),
      });
    }
    await refresh(advId);
  }

  return (
    <main>
      <p className="muted">
        AI plans campaigns asynchronously. The Go bidder only reads a compiled Redis snapshot — never Postgres or an LLM.
      </p>
      <div className="grid">
        <section className="card">
          <h2>1. Onboarding</h2>
          <form onSubmit={onSignup}>
            <label>Company</label>
            <input value={company} onChange={(e) => setCompany(e.target.value)} />
            <label>Email</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} />
            <button type="submit">Create advertiser</button>
          </form>
          <label>Active advertiser</label>
          <select value={advId} onChange={(e) => { const id = Number(e.target.value); setAdvId(id); refresh(id); }}>
            {advertisers.map((a) => (
              <option key={a.id} value={a.id}>{a.company} (#{a.id})</option>
            ))}
          </select>
        </section>

        <section className="card">
          <h2>2. Creative vs JCDecaux / VIOOH specs</h2>
          <form onSubmit={onUpload}>
            <label>Screen spec</label>
            <select value={specId} onChange={(e) => setSpecId(Number(e.target.value))}>
              {specs.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.publisher} {s.format_code} {s.width}x{s.height} {s.country}
                </option>
              ))}
            </select>
            <label>Asset</label>
            <input type="file" name="file" accept="image/*,video/mp4" required />
            <button type="submit">Validate & upload</button>
          </form>
          <table>
            <thead><tr><th>ID</th><th>File</th><th>Status</th></tr></thead>
            <tbody>
              {creatives.map((c) => (
                <tr key={c.id}>
                  <td>{c.id}</td>
                  <td>{c.filename}</td>
                  <td className={c.validation_status === "valid" ? "ok" : "bad"}>{c.validation_status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="card">
          <h2>3. Campaign + agent plan</h2>
          <form onSubmit={onCreateCampaign}>
            <label>Name</label>
            <input value={campName} onChange={(e) => setCampName(e.target.value)} />
            <button type="submit">Create draft campaign</button>
          </form>
          <label>Campaign</label>
          <select value={campId} onChange={(e) => setCampId(Number(e.target.value))}>
            {campaigns.map((c) => (
              <option key={c.id} value={c.id}>{c.name} · {c.state}</option>
            ))}
          </select>
          <p className="muted">State: {selectedCamp?.state || "none"}</p>
          <button type="button" className="secondary" onClick={() => setState("pending_approval")}>Submit for approval</button>
          <button type="button" onClick={() => setState("active")}>Activate (compile rules)</button>
          <button type="button" className="secondary" onClick={() => setState("paused")}>Pause</button>
          <form onSubmit={onChat}>
            <label>Ask the campaign agent</label>
            <textarea rows={3} value={chat} onChange={(e) => setChat(e.target.value)} />
            <button type="submit">Draft plan</button>
          </form>
          <div className="chat">{reply || "Agent replies appear here. Plans are never executed on the bid path."}</div>
        </section>

        <section className="card">
          <h2>4. Spend & proof-of-play</h2>
          <p className="chat">{insight || "No analytics yet."}</p>
          <table>
            <thead><tr><th>Hour</th><th>Type</th><th>Bids</th><th>Imps</th><th>Spend µ</th></tr></thead>
            <tbody>
              {hourly.slice(0, 12).map((h, i) => (
                <tr key={i}>
                  <td>{String(h.hour)}</td>
                  <td>{h.event_type}</td>
                  <td>{h.bids}</td>
                  <td>{Number(h.imps).toFixed(1)}</td>
                  <td>{h.spend_micros}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">{status}</p>
        </section>
      </div>
    </main>
  );
}
