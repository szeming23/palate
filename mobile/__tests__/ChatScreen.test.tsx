import { fireEvent, render, screen } from "@testing-library/react-native";

import ChatScreen from "../app/index";
import * as api from "../lib/api";

jest.mock("../lib/api");
jest.mock("expo-location", () => ({
  requestForegroundPermissionsAsync: jest.fn(async () => ({ status: "denied" })),
  getForegroundPermissionsAsync: jest.fn(async () => ({ status: "denied" })),
  Accuracy: { Balanced: 3 },
}));
jest.mock("expo-router", () => ({
  useFocusEffect: (cb: () => void) => require("react").useEffect(cb, [cb]),
}));

const mocked = (fn: unknown) => fn as jest.Mock;
const card = { place_id: "p1", recommendation_id: 9, name: "Tian Tian", reason: "Classic" };

beforeEach(() => {
  jest.clearAllMocks();
  mocked(api.getHistory).mockResolvedValue({ messages: [] });
});

test("shows a prompt when there's no history", async () => {
  await render(<ChatScreen />);
  expect(await screen.findByText(/What are you craving\?/)).toBeTruthy();
});

test("loads chat history", async () => {
  mocked(api.getHistory).mockResolvedValue({
    messages: [
      { id: 1, role: "user", content: "chicken rice", cards: [] },
      { id: 2, role: "assistant", content: "Try these:", cards: [card] },
    ],
  });
  await render(<ChatScreen />);
  expect(await screen.findByText("Try these:")).toBeTruthy();
  expect(screen.getByText("Tian Tian")).toBeTruthy();
});

test("sends a message and shows the reply with cards", async () => {
  mocked(api.sendChat).mockResolvedValue({ id: 5, reply: "Here you go", cards: [card] });
  await render(<ChatScreen />);
  await fireEvent.changeText(screen.getByPlaceholderText("What do you feel like eating?"), "  chicken rice ");
  await fireEvent.press(screen.getByText("Send"));
  expect(await screen.findByText("Here you go")).toBeTruthy();
  expect(screen.getByText("chicken rice")).toBeTruthy();
  expect(screen.getByText("Tian Tian")).toBeTruthy();
  // Location permission was denied, so no coordinates are sent.
  expect(api.sendChat).toHaveBeenCalledWith("chicken rice", undefined);
});

test("a failed send shows the error and puts the text back", async () => {
  mocked(api.sendChat).mockRejectedValue(new Error("Daily limit reached"));
  await render(<ChatScreen />);
  const input = screen.getByPlaceholderText("What do you feel like eating?");
  await fireEvent.changeText(input, "laksa");
  await fireEvent.press(screen.getByText("Send"));
  expect(await screen.findByText("Daily limit reached")).toBeTruthy();
  expect(screen.getByDisplayValue("laksa")).toBeTruthy();
});

test("shows an error when history can't load", async () => {
  mocked(api.getHistory).mockRejectedValue(new Error("Set the Palate server URL in Settings."));
  await render(<ChatScreen />);
  expect(await screen.findByText("Set the Palate server URL in Settings.")).toBeTruthy();
});
