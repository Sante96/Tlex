import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://backend:8000";

async function proxyStream(request: NextRequest, path: string) {
  const url = new URL(request.url);
  const params = new URLSearchParams(url.search);
  params.delete("path");
  const queryString = params.toString();
  const backendUrl = `${BACKEND_URL}/api/v1/stream/${path}${queryString ? `?${queryString}` : ""}`;

  const headers = new Headers();
  const rangeHeader = request.headers.get("range");
  if (rangeHeader) {
    headers.set("Range", rangeHeader);
  }

  // Combined abort: timeout (30s) + client disconnect propagation
  // This is critical — without forwarding request.signal, the backend
  // connection stays open when the browser cancels (seek, navigation),
  // creating zombie connections that hold Telegram workers
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  const onAbort = () => controller.abort();
  request.signal.addEventListener("abort", onAbort);

  try {
    const response = await fetch(backendUrl, {
      method: request.method,
      headers,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    // For HEAD requests, return immediately
    if (request.method === "HEAD") {
      const responseHeaders = new Headers();
      response.headers.forEach((value, key) => {
        responseHeaders.set(key, value);
      });
      return new Response(null, {
        status: response.status,
        headers: responseHeaders,
      });
    }

    // Forward response headers
    const responseHeaders = new Headers();
    response.headers.forEach((value, key) => {
      responseHeaders.set(key, value);
    });
    responseHeaders.set("X-Accel-Buffering", "no");
    responseHeaders.set("Cache-Control", "no-cache, no-store, must-revalidate");

    if (!response.body) {
      return new Response(null, { status: 204 });
    }

    // Stream body with proper cleanup on client disconnect
    const reader = response.body.getReader();
    const stream = new ReadableStream({
      async pull(streamController) {
        try {
          const { done, value } = await reader.read();
          if (done) {
            streamController.close();
          } else {
            streamController.enqueue(value);
          }
        } catch {
          streamController.close();
        }
      },
      cancel() {
        reader.cancel();
        controller.abort();
      },
    });

    return new Response(stream, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch {
    // Client-initiated abort (seek/navigation) is not an error
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

// Use Node.js runtime for better streaming support
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
