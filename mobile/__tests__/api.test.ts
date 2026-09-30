import { secureStoreMock } from "../test-utils/secureStoreMock";
jest.mock("expo-secure-store", () => require("../test-utils/secureStoreMock").secureStoreMock);

import { getModels, getMe, sendChat, sendFeedback } from "../lib/api";
import { DEFAULT_SETTINGS, saveSettings } from "../lib/settings";

const fetchMock = jest.fn();
globalThis.fetch = fetchMock as unknown as typeof fetch;

function reply(status: number, body: unknown) {
  return { ok: status < 400, status, json: async () => body };
}

async function useSettings(over: Partial<typeof DEFAULT_SETTINGS> = {}) {
  await saveSettings({ ...DEFAULT_SETTINGS, backendUrl: "https://palate.test/", accessCode: "plt_abc", ...over });
}

beforeEach(() => {
  secureStoreMock.reset();
  fetchMock.mockReset();
});

test("fails with a clear message when no server URL is set", async () => {
  await expect(getMe()).rejects.toThrow("Set the Palate server URL in Settings.");
  expect(fetchMock).not.toHaveBeenCalled();
});

test("sends the access code as a bearer token and trims the trailing slash", async () => {
  await useSettings();
  fetchMock.mockResolvedValue(reply(200, { name: "me" }));
  await getMe();
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("https://palate.test/me");
  expect(init.headers.Authorization).toBe("Bearer plt_abc");
});

test("uses the server's error detail when there is one", async () => {
  await useSettings();
  fetchMock.mockResolvedValue(reply(429, { detail: "Daily limit reached" }));
  await expect(getMe()).rejects.toThrow("Daily limit reached");
});

test("falls back to the status code when the error body isn't JSON", async () => {
  await useSettings();
  fetchMock.mockResolvedValue({ ok: false, status: 502, json: async () => Promise.reject(new Error("bad")) });
  await expect(getMe()).rejects.toThrow("Server error 502");
});

test("explains when the server can't be reached", async () => {
  await useSettings();
  fetchMock.mockRejectedValue(new TypeError("Network request failed"));
  await expect(getMe()).rejects.toThrow("Can't reach the Palate server at https://palate.test/");
});

test("chat sends the model and coordinates, and the own key only as a header", async () => {
  await useSettings({ model: "claude-haiku-4-5", ownApiKey: "sk-own" });
  fetchMock.mockResolvedValue(reply(200, { id: 1, reply: "hi", cards: [] }));
  await sendChat("chicken rice", { lat: 1.35, lng: 103.8 });
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("https://palate.test/chat");
  expect(init.method).toBe("POST");
  expect(init.headers["X-LLM-API-Key"]).toBe("sk-own");
  expect(JSON.parse(init.body)).toEqual({ message: "chicken rice", model: "claude-haiku-4-5", lat: 1.35, lng: 103.8 });
});

test("chat without an own key sends no key header", async () => {
  await useSettings();
  fetchMock.mockResolvedValue(reply(200, { id: 1, reply: "hi", cards: [] }));
  await sendChat("laksa");
  expect(fetchMock.mock.calls[0][1].headers["X-LLM-API-Key"]).toBeUndefined();
});

test("models asks for own-key models only when an own key is set", async () => {
  await useSettings();
  fetchMock.mockResolvedValue(reply(200, { default: null, models: [] }));
  await getModels();
  expect(fetchMock.mock.calls[0][0]).toBe("https://palate.test/models");

  await useSettings({ ownApiKey: "sk-own" });
  await getModels();
  expect(fetchMock.mock.calls[1][0]).toBe("https://palate.test/models?own_key_provider=anthropic");
});

test("feedback is a PUT with the vote in the body", async () => {
  await useSettings();
  fetchMock.mockResolvedValue(reply(200, {}));
  await sendFeedback(7, "up");
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("https://palate.test/recommendations/7/feedback");
  expect(init.method).toBe("PUT");
  expect(JSON.parse(init.body)).toEqual({ feedback: "up" });
});
