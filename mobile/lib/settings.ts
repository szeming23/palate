import * as SecureStore from "expo-secure-store";

// Stored in Android Keystore-backed encrypted storage on the device.
export type Settings = {
  backendUrl: string; // e.g. https://xyz.trycloudflare.com, or http://<LAN IP>:8000 on home Wi-Fi
  accessCode: string; // from `python -m palate.admin codes add` on the server
  model: string;
  ownApiKey: string; // optional: pay with your own Claude key instead of the server's
};

const KEYS: Record<keyof Settings, string> = {
  backendUrl: "palate.backendUrl",
  accessCode: "palate.accessCode",
  model: "palate.model",
  ownApiKey: "palate.ownApiKey",
};

export const DEFAULT_SETTINGS: Settings = {
  backendUrl: "", // no default: the user must enter their own server
  accessCode: "",
  model: "claude-opus-5",
  ownApiKey: "",
};

export async function loadSettings(): Promise<Settings> {
  const entries = await Promise.all(
    (Object.keys(KEYS) as (keyof Settings)[]).map(async (k) => {
      const v = await SecureStore.getItemAsync(KEYS[k]);
      return [k, v ?? DEFAULT_SETTINGS[k]] as const;
    }),
  );
  return Object.fromEntries(entries) as Settings;
}

export async function saveSettings(s: Settings): Promise<void> {
  await Promise.all(
    (Object.keys(KEYS) as (keyof Settings)[]).map((k) => SecureStore.setItemAsync(KEYS[k], s[k])),
  );
}

// True for plain-http URLs that leave the local network, where the access code would travel unencrypted.
// http is fine for localhost and private LAN addresses (10.x, 172.16-31.x, 192.168.x).
export function isInsecureRemoteUrl(url: string): boolean {
  const m = /^http:\/\/([^/:?#]+)/i.exec(url.trim());
  if (!m) return false;
  const host = m[1].toLowerCase();
  const isPrivate =
    host === "localhost" ||
    /^127\./.test(host) ||
    /^10\./.test(host) ||
    /^192\.168\./.test(host) ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(host);
  return !isPrivate;
}
