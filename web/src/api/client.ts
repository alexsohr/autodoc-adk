export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ApiFetchOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  params?: Record<string, string | number | boolean | undefined>;
}

async function apiFetch<T>(
  path: string,
  options?: ApiFetchOptions,
): Promise<T> {
  const { params, body, headers: customHeaders, ...fetchOptions } =
    options ?? {};

  // Build query string from params, filtering out undefined values
  let url = `/api${path}`;
  if (params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) {
        searchParams.set(key, String(value));
      }
    }
    const qs = searchParams.toString();
    if (qs) {
      url = `${url}?${qs}`;
    }
  }

  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...customHeaders,
    },
    ...fetchOptions,
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });

  if (!response.ok) {
    const responseBody = await response.json().catch(() => null);
    throw new ApiError(response.status, response.statusText, responseBody);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(
    path: string,
    options?: { params?: Record<string, string | number | boolean | undefined> },
  ) => apiFetch<T>(path, options),

  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: "POST", body }),

  patch: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: "PATCH", body }),

  put: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: "PUT", body }),

  delete: <T>(path: string) =>
    apiFetch<T>(path, { method: "DELETE" }),
};
