import { secureStoreMock } from "../test-utils/secureStoreMock";
jest.mock("expo-secure-store", () => require("../test-utils/secureStoreMock").secureStoreMock);

import { DEFAULT_SETTINGS, isInsecureRemoteUrl, loadSettings, saveSettings } from "../lib/settings";

beforeEach(() => secureStoreMock.reset());

test("returns defaults when nothing is saved", async () => {
  expect(await loadSettings()).toEqual(DEFAULT_SETTINGS);
});

test("there is no default server URL, so the user must enter their own", () => {
  expect(DEFAULT_SETTINGS.backendUrl).toBe("");
});

test("saved settings load back unchanged", async () => {
  const s = { backendUrl: "https://x.trycloudflare.com", accessCode: "plt_abc", model: "m", ownApiKey: "sk-1" };
  await saveSettings(s);
  expect(await loadSettings()).toEqual(s);
});

describe("isInsecureRemoteUrl", () => {
  test.each([
    ["http://192.168.1.2:8000", false],
    ["http://10.0.0.5", false],
    ["http://172.20.1.1:8000", false],
    ["http://localhost:8000", false],
    ["http://127.0.0.1:8000", false],
    ["https://x.trycloudflare.com", false],
    ["", false],
    ["http://example.com", true],
    ["HTTP://Example.com/path", true],
    ["http://172.40.1.1", true], // outside 172.16-31
    ["http://8.8.8.8:8000", true],
  ])("%s -> %s", (url, insecure) => {
    expect(isInsecureRemoteUrl(url)).toBe(insecure);
  });
});
