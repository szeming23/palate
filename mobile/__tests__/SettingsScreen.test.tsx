import { fireEvent, render, screen } from "@testing-library/react-native";

import SettingsScreen from "../app/settings";
import * as api from "../lib/api";
import * as settings from "../lib/settings";

jest.mock("../lib/api");
jest.mock("../lib/settings", () => ({
  ...jest.requireActual("../lib/settings"),
  loadSettings: jest.fn(),
  saveSettings: jest.fn(),
}));
jest.mock("@react-native-picker/picker", () => {
  const { Text } = require("react-native");
  const Picker = ({ children }: any) => children;
  Picker.Item = ({ label }: any) => <Text>{label}</Text>;
  return { Picker };
});

const mocked = <T extends (...args: any[]) => any>(fn: T) => fn as unknown as jest.Mock;

const saved = { backendUrl: "https://palate.test", accessCode: "plt_abc", model: "old-model", ownApiKey: "" };
const me = { name: "my-phone", user_id: "me", daily_messages: 50, daily_usd: 3, today: { messages: 2, cost_usd: 0.1 } };
const profile = { dietary: "", allergies: "", budget: "", likes: "", dislikes: "", notes: "" };

function serverUp() {
  mocked(api.getMe).mockResolvedValue(me);
  mocked(api.getModels).mockResolvedValue({
    default: "claude-haiku-4-5",
    models: [{ id: "claude-haiku-4-5", provider: "anthropic", label: "Claude Haiku 4.5" }],
  });
  mocked(api.getProfile).mockResolvedValue(profile);
  mocked(api.getMemories).mockResolvedValue({ memories: [{ id: 1, kind: "fact", content: "dislikes coriander", created_at: "" }] });
}

beforeEach(() => {
  jest.clearAllMocks();
  mocked(settings.loadSettings).mockResolvedValue(saved);
  mocked(settings.saveSettings).mockResolvedValue(undefined);
  serverUp();
});

test("on open, loads saved settings and connects to the server", async () => {
  await render(<SettingsScreen />);
  expect(await screen.findByText(/Connected as “my-phone” ✓/)).toBeTruthy();
  expect(screen.getByText(/2\/50 messages, US\$0.10 of US\$3.00 used/)).toBeTruthy();
  expect(screen.getByText("dislikes coriander")).toBeTruthy();
  expect(screen.getByDisplayValue("https://palate.test")).toBeTruthy();
});

test("switches to the server's default model when the saved one isn't allowed", async () => {
  await render(<SettingsScreen />);
  await screen.findByText(/Connected as/);
  expect(settings.saveSettings).toHaveBeenCalledWith({ ...saved, model: "claude-haiku-4-5" });
});

test("shows an error if saved settings can't be read", async () => {
  mocked(settings.loadSettings).mockRejectedValue(new Error("keystore locked"));
  await render(<SettingsScreen />);
  expect(await screen.findByText("Couldn't load saved settings: keystore locked")).toBeTruthy();
  expect(api.getMe).not.toHaveBeenCalled();
});

test("shows the server error when it can't connect", async () => {
  mocked(api.getMe).mockRejectedValue(new Error("Invalid access code"));
  await render(<SettingsScreen />);
  expect(await screen.findByText("Invalid access code")).toBeTruthy();
  expect(screen.getByText("Connect to see the models your access code can use.")).toBeTruthy();
});

test("warns about an http URL outside the local network, but not a LAN one", async () => {
  await render(<SettingsScreen />);
  await screen.findByText(/Connected as/);
  const warning = /access code would be sent unencrypted/;
  const url = screen.getByDisplayValue("https://palate.test");

  await fireEvent.changeText(url, "http://192.168.1.2:8000");
  expect(screen.queryByText(warning)).toBeNull();

  await fireEvent.changeText(url, "http://palate.example.com");
  expect(screen.getByText(warning)).toBeTruthy();
});
