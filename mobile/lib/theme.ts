import { useColorScheme } from "react-native";

const light = {
  bg: "#FAF7F2",
  surface: "#FFFFFF",
  text: "#1F1A17",
  muted: "#7A716B",
  border: "#E8E1D9",
  accent: "#D9480F",
  accentText: "#FFFFFF",
  userBubble: "#D9480F",
  good: "#2B8A3E",
  bad: "#C92A2A",
};

const dark: typeof light = {
  bg: "#161312",
  surface: "#221E1C",
  text: "#F4EEE9",
  muted: "#A39A93",
  border: "#3A3431",
  accent: "#FF6B2C",
  accentText: "#161312",
  userBubble: "#FF6B2C",
  good: "#51CF66",
  bad: "#FF6B6B",
};

export type Theme = typeof light;

export function useTheme(): Theme {
  return useColorScheme() === "dark" ? dark : light;
}
