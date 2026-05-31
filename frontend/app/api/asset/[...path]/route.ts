// Server-to-server proxy to the remote asset service.
//
// The browser otherwise has to make cross-origin requests to the asset host,
// and any time the upstream returns 5xx (or transiently goes down) the
// browser reports it as a CORS failure because error responses don't carry
// Access-Control-Allow-Origin headers. Routing through this Next.js route
// makes every browser call same-origin (zero CORS) and proxies the body /
// headers back unmodified.
//
// Only POST request bodies are forwarded; we don't bother proxying PNG
// downloads since `<img src>` and SVG `<image href>` aren't CORS-restricted
// for display — those still go direct to the asset host via
// `absoluteAssetUrl()`.

import { NextRequest, NextResponse } from "next/server";

const ASSET_BASE = (process.env.NEXT_PUBLIC_ASSET_API_URL ?? "").replace(
  /\/+$/,
  "",
);

// Hop-by-hop or content-negotiation headers that must be re-derived per hop.
// We also strip `accept-encoding` from the upstream request: if we forward
// the browser's Accept-Encoding, the upstream will reply with compressed
// bytes — and the runtime's fetch may or may not auto-decompress before
// arrayBuffer(), leaving the browser to receive raw compressed bytes with no
// content-encoding hint and rendering them as garbage. Simpler to ask
// upstream for identity (uncompressed) end-to-end.
const STRIP_REQ = new Set([
  "host",
  "connection",
  "content-length",
  "accept-encoding",
]);
const STRIP_RES = new Set([
  "content-encoding",
  "transfer-encoding",
  "connection",
  "content-length",
]);

async function proxy(req: NextRequest, segments: string[]): Promise<NextResponse> {
  if (!ASSET_BASE) {
    return NextResponse.json(
      { detail: "NEXT_PUBLIC_ASSET_API_URL is not configured" },
      { status: 503 },
    );
  }

  const path = "/" + segments.join("/");
  const target = `${ASSET_BASE}${path}${req.nextUrl.search}`;

  const headers = new Headers();
  for (const [k, v] of req.headers.entries()) {
    if (STRIP_REQ.has(k.toLowerCase())) continue;
    headers.set(k, v);
  }
  // Override Origin so the upstream sees the deployed app's origin, not the
  // dev server. Cosmetic — most upstreams ignore Origin, but it keeps logs
  // sensible.
  headers.delete("origin");

  const body =
    req.method === "GET" || req.method === "HEAD" ? undefined : await req.text();

  try {
    const upstream = await fetch(target, {
      method: req.method,
      headers,
      body,
      cache: "no-store",
    });
    const buffer = await upstream.arrayBuffer();
    const respHeaders = new Headers();
    upstream.headers.forEach((v, k) => {
      if (STRIP_RES.has(k.toLowerCase())) return;
      respHeaders.set(k, v);
    });
    return new NextResponse(buffer, {
      status: upstream.status,
      headers: respHeaders,
    });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      { detail: `asset proxy fetch failed: ${message}` },
      { status: 502 },
    );
  }
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function POST(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function DELETE(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}
