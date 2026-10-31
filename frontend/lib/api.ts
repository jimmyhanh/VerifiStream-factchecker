export const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
).replace(/\/$/, "");
export async function api<T>(
  path: string,
  body?: object | FormData,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: body === undefined ? "GET" : "POST",
      cache: "no-store",
      credentials: "omit",
      headers:
        body !== undefined && !(body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : undefined,
      body:
        body === undefined
          ? undefined
          : body instanceof FormData
            ? body
            : JSON.stringify(body),
    });
  } catch {
    throw new Error(
      "Could not reach the backend. Check that Docker is running and the API address/CORS origin match. A submitted operation may still be running; refresh saved runs before trying again.",
    );
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? "Check the selected items and input values."
          : detail?.message;
    throw new Error(
      `${message || "Request failed."}${detail?.code ? ` (${detail.code})` : ""} [HTTP ${response.status}]`,
    );
  }
  if (payload === null)
    throw new Error(
      "The backend returned an unreadable response. Refresh saved runs before retrying.",
    );
  return payload as T;
}
export function safeLink(value: string): string | undefined {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) &&
      !url.username &&
      !url.password
      ? url.href
      : undefined;
  } catch {
    return undefined;
  }
}
export function timecode(seconds: number): string {
  const n = Math.floor(seconds);
  return `${Math.floor(n / 60)}:${String(n % 60).padStart(2, "0")}`;
}
