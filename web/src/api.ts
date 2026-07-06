const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000/api";
const STORAGE_KEY = "ldv.apiBase";

export function getApiBase(): string {
  const queryValue = new URLSearchParams(window.location.search).get("api");
  if (queryValue) {
    localStorage.setItem(STORAGE_KEY, queryValue);
    return queryValue;
  }
  return localStorage.getItem(STORAGE_KEY) || DEFAULT_API_BASE;
}

export function setApiBase(value: string): void {
  const normalized = value.trim().replace(/\/$/, "");
  if (normalized) {
    localStorage.setItem(STORAGE_KEY, normalized);
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${getApiBase()}${path}`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export async function apiPost<T = unknown>(path: string): Promise<T> {
  const response = await fetch(`${getApiBase()}${path}`, { method: "POST" });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export function videoUrl(datasetId: string, taskId: string, episodeIndex: number, cameraKey: string): string {
  return `${getApiBase()}/datasets/${encodeURIComponent(datasetId)}/tasks/${encodeURIComponent(taskId)}/episodes/${episodeIndex}/videos/${encodeURIComponent(cameraKey)}`;
}
