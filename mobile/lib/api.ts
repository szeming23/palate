import { loadSettings } from "./settings";

export type PlaceCard = {
  place_id: string;
  recommendation_id: number;
  name: string;
  address?: string;
  type?: string;
  rating?: number;
  rating_count?: number;
  price?: string;
  open_now?: boolean;
  maps_url?: string;
  distance_m?: number;
  reason: string;
};

export type ChatMessage = {
  id: number | string;
  role: "user" | "assistant";
  content: string;
  cards: PlaceCard[];
};

export type ModelInfo = { id: string; provider: string; label: string };

export type Profile = {
  dietary: string;
  allergies: string;
  budget: string;
  likes: string;
  dislikes: string;
  notes: string;
};

export type Me = {
  name: string;
  user_id: string;
  daily_messages: number | null;
  daily_usd: number | null;
  today: { messages: number; cost_usd: number };
};

export type Memory = { id: number; kind: "fact" | "location"; content: string; created_at: string };

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const s = await loadSettings();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  };
  if (s.accessCode) headers.Authorization = `Bearer ${s.accessCode}`;

  let res: Response;
  try {
    res = await fetch(`${s.backendUrl.replace(/\/$/, "")}${path}`, { ...init, headers });
  } catch {
    throw new Error(`Can't reach the Palate server at ${s.backendUrl}. Check Settings.`);
  }
  if (!res.ok) {
    let detail = `Server error ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}

export async function sendChat(message: string, coords?: { lat: number; lng: number }) {
  const s = await loadSettings();
  return request<{ id: number; reply: string; cards: PlaceCard[] }>("/chat", {
    method: "POST",
    headers: s.ownApiKey ? { "X-LLM-API-Key": s.ownApiKey } : {},
    body: JSON.stringify({ message, model: s.model, ...coords }),
  });
}

export const getHistory = () => request<{ messages: ChatMessage[] }>("/history");
export const clearHistory = () => request("/history", { method: "DELETE" });
export async function getModels() {
  const s = await loadSettings();
  // With an own key, the server also lists that provider's models even if the code has no server key for it.
  const q = s.ownApiKey ? "?own_key_provider=anthropic" : "";
  return request<{ default: string | null; models: ModelInfo[] }>(`/models${q}`);
}
export const getMe = () => request<Me>("/me");
export const getProfile = () => request<Profile>("/profile");
export const saveProfile = (p: Profile) =>
  request<Profile>("/profile", { method: "PUT", body: JSON.stringify(p) });
export const getMemories = () => request<{ memories: Memory[] }>("/memories");
export const deleteMemory = (id: number) => request(`/memories/${id}`, { method: "DELETE" });
export const sendFeedback = (recId: number, feedback: "up" | "down" | null) =>
  request(`/recommendations/${recId}/feedback`, { method: "PUT", body: JSON.stringify({ feedback }) });
