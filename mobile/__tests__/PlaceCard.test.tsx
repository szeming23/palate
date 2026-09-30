import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import PlaceCard from "../components/PlaceCard";
import { PlaceCard as Card, sendFeedback } from "../lib/api";

jest.mock("../lib/api", () => ({ sendFeedback: jest.fn() }));
const sendFeedbackMock = sendFeedback as jest.Mock;

const card: Card = {
  place_id: "p1",
  recommendation_id: 7,
  name: "Tian Tian Chicken Rice",
  rating: 4.4,
  rating_count: 1200,
  price: "$",
  open_now: true,
  distance_m: 1500,
  reason: "Classic Hainanese, short walk",
};

beforeEach(() => sendFeedbackMock.mockReset());

test("shows the place details", async () => {
  await render(<PlaceCard card={card} />);
  expect(screen.getByText("Tian Tian Chicken Rice")).toBeTruthy();
  expect(screen.getByText("★ 4.4 (1200)  ·  $  ·  1.5 km  ·  Open now")).toBeTruthy();
  expect(screen.getByText("Classic Hainanese, short walk")).toBeTruthy();
});

test("a vote is sent and shown as selected", async () => {
  sendFeedbackMock.mockResolvedValue({});
  await render(<PlaceCard card={card} />);
  await fireEvent.press(screen.getByLabelText("Good pick"));
  expect(sendFeedbackMock).toHaveBeenCalledWith(7, "up");
  expect(screen.getByLabelText("Good pick")).toBeSelected();
});

test("tapping the same vote again clears it", async () => {
  sendFeedbackMock.mockResolvedValue({});
  await render(<PlaceCard card={card} />);
  await fireEvent.press(screen.getByLabelText("Good pick"));
  await fireEvent.press(screen.getByLabelText("Good pick"));
  expect(sendFeedbackMock).toHaveBeenLastCalledWith(7, null);
  expect(screen.getByLabelText("Good pick")).not.toBeSelected();
});

test("a failed vote reverts to the previous choice", async () => {
  sendFeedbackMock.mockResolvedValueOnce({}).mockRejectedValueOnce(new Error("offline"));
  await render(<PlaceCard card={card} />);
  await fireEvent.press(screen.getByLabelText("Good pick"));
  await fireEvent.press(screen.getByLabelText("Bad pick"));
  await waitFor(() => expect(screen.getByLabelText("Good pick")).toBeSelected());
  expect(screen.getByLabelText("Bad pick")).not.toBeSelected();
});
