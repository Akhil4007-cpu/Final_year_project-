const CLIENT_HEADER = "X-RoadGuard-Client";
const CLIENT_VALUE = "web";

export class ApiError extends Error {
  constructor(status, code, message, details = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export async function api(path, { method = "GET", body, signal } = {}) {
  const options = {
    method,
    credentials: "same-origin",
    headers: { Accept: "application/json", [CLIENT_HEADER]: CLIENT_VALUE },
    signal,
  };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(0, "network_error", "Network unavailable. Check your connection.");
  }
  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }
  if (!response.ok) {
    const detail = payload && payload.error ? payload.error : {};
    throw new ApiError(
      response.status,
      detail.code || "internal_error",
      detail.message || `Request failed (${response.status}).`,
      detail.details || null,
    );
  }
  return payload;
}

export function getJson(path, signal) {
  return api(path, { signal });
}

export function postJson(path, body, signal) {
  return api(path, { method: "POST", body, signal });
}

export function deleteJson(path) {
  return api(path, { method: "DELETE" });
}
