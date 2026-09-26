import * as SecureStore from "expo-secure-store";

// Stored in Android Keystore-backed encrypted storage on the device.
export type Settings = {
  backendUrl: string; // e.g. http://192.168.1.20:8000
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
  backendUrl: "http://192.168.1.2:8000",
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
