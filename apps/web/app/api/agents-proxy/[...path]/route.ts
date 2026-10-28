import { NextRequest } from "next/server";

const UPSTREAM = process.env.AGENTS_INTERNAL_URL || process.env.NEXT_PUBLIC_AGENTS_URL || "http://localhost:8091";

async function proxy(req: NextRequest, path: string[]) {
  const search = req.nextUrl.search;
  const url = `${UPSTREAM.replace(/\/$/, "")}/${path.join("/")}${search}`;
  const headers: Record<string, string> = {};
  const ctype = req.headers.get("content-type");
  if (ctype) headers["content-type"] = ctype;
  const init: RequestInit = { method: req.method, headers, cache: "no-store" };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.text();
  }
  const res = await fetch(url, init);
  const body = await res.arrayBuffer();
  return new Response(body, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") || "application/json" },
  });
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return proxy(req, path);
}
