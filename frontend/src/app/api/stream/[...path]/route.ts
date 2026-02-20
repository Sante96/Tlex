import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

// Headers to forward from the client request to the backend
const FORWARD_HEADERS = ["range", "authorization"] as const;

async function proxyStream(request: NextRequest, path: string) {
  const query = new URL(request.url).search;
  const backendUrl = `${BACKEND_URL}/api/v1/stream/${path}${query}`;

  // Forward relevant headers
  const headers = new Headers();
  for (const key of FORWARD_HEADERS) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }

  // Abort chain: client disconnect → controller.abort() → backend fetch cancelled
  // 60s timeout covers FFmpeg probe time through slow Telegram connections
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000);
  const onAbort = () => controller.abort();
  request.signal.addEventListener("abort", onAbort);

  try {
    const response = await fetch(backendUrl, {
      method: request.method,
      headers,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    // Forward response headers
    const responseHeaders = new Headers(response.headers);
    responseHeaders.set("X-Accel-Buffering", "no");
    responseHeaders.set("Cache-Control", "no-cache, no-store, must-revalidate");

    // Direct body pass-through — zero-copy streaming, no ReadableStream wrapper
    // Cleanup chain: client disconnects → request.signal aborts → controller aborts
    // → backend fetch aborted → response.body stream cancelled automatically
    return new Response(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch {
    if (request.signal.aborted) {
      return new Response(null, { status: 499 });
    }
    return new Response("Stream proxy error", { status: 502 });
  } finally {
    clearTimeout(timeoutId);
    request.signal.removeEventListener("abort", onAbort);
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyStream(request, path.join("/"));
}

export async function HEAD(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyStream(request, path.join("/"));
}

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
