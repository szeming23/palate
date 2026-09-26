import { Link, Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { Text } from "react-native";

import { useTheme } from "../lib/theme";

export default function RootLayout() {
  const t = useTheme();
  return (
    <>
      <StatusBar style="auto" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: t.surface },
          headerTintColor: t.text,
          contentStyle: { backgroundColor: t.bg },
        }}
      >
        <Stack.Screen
          name="index"
          options={{
            title: "Palate",
            headerRight: () => (
              <Link href="/settings" style={{ color: t.accent, fontSize: 16, fontWeight: "600" }}>
                <Text>Settings</Text>
              </Link>
            ),
          }}
        />
        <Stack.Screen name="settings" options={{ title: "Settings" }} />
      </Stack>
    </>
  );
}
