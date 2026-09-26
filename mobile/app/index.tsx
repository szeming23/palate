import * as Location from "expo-location";
import { useFocusEffect } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import PlaceCard from "../components/PlaceCard";
import { ChatMessage, getHistory, sendChat } from "../lib/api";
import { useTheme } from "../lib/theme";

async function currentCoords(): Promise<{ lat: number; lng: number } | undefined> {
  const { status } = await Location.getForegroundPermissionsAsync();
  if (status !== "granted") return undefined;
  const pos =
    (await Location.getLastKnownPositionAsync({ maxAge: 5 * 60_000 })) ??
    (await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }));
  return pos ? { lat: pos.coords.latitude, lng: pos.coords.longitude } : undefined;
}

export default function ChatScreen() {
  const t = useTheme();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [useLocation, setUseLocation] = useState(true);
  const listRef = useRef<FlatList<ChatMessage>>(null);

  useEffect(() => {
    Location.requestForegroundPermissionsAsync().then(({ status }) => {
      if (status !== "granted") setUseLocation(false);
    });
  }, []);

  // Reload history when returning from Settings (e.g. after changing server).
  useFocusEffect(
    useCallback(() => {
      getHistory()
        .then((r) => {
          setMessages(r.messages);
          setError(null);
        })
        .catch((e) => setError(e.message));
    }, []),
  );

  async function send() {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setError(null);
    setSending(true);
    const pending: ChatMessage = { id: `local-${Date.now()}`, role: "user", content: text, cards: [] };
    setMessages((m) => [...m, pending]);
    try {
      const coords = useLocation ? await currentCoords().catch(() => undefined) : undefined;
      const res = await sendChat(text, coords);
      setMessages((m) => [...m, { id: res.id, role: "assistant", content: res.reply, cards: res.cards }]);
    } catch (e: any) {
      setMessages((m) => m.filter((x) => x.id !== pending.id));
      setInput(text);
      setError(e.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: t.bg }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(m) => String(m.id)}
        contentContainerStyle={styles.list}
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
        ListEmptyComponent={
          <Text style={[styles.empty, { color: t.muted }]}>
            What are you craving? Try “bishan chicken rice” or “cheap dinner near me”.
          </Text>
        }
        renderItem={({ item }) =>
          item.role === "user" ? (
            <View style={[styles.bubble, styles.userBubble, { backgroundColor: t.userBubble }]}>
              <Text style={{ color: t.accentText, fontSize: 15 }}>{item.content}</Text>
            </View>
          ) : (
            <View style={styles.assistant}>
              <Text style={{ color: t.text, fontSize: 15, lineHeight: 21 }}>{item.content}</Text>
              {item.cards.map((c) => (
                <PlaceCard key={c.recommendation_id} card={c} />
              ))}
            </View>
          )
        }
        ListFooterComponent={
          sending ? <ActivityIndicator style={{ marginVertical: 12 }} color={t.accent} /> : null
        }
      />

      {error ? <Text style={[styles.error, { color: t.bad }]}>{error}</Text> : null}

      <View style={[styles.inputRow, { borderColor: t.border, backgroundColor: t.surface }]}>
        <Pressable
          onPress={() => setUseLocation((v) => !v)}
          hitSlop={8}
          accessibilityLabel={useLocation ? "Location on" : "Location off"}
        >
          <Text style={{ fontSize: 20, opacity: useLocation ? 1 : 0.3 }}>📍</Text>
        </Pressable>
        <TextInput
          style={[styles.input, { color: t.text }]}
          value={input}
          onChangeText={setInput}
          placeholder="What do you feel like eating?"
          placeholderTextColor={t.muted}
          onSubmitEditing={send}
          returnKeyType="send"
          editable={!sending}
        />
        <Pressable onPress={send} disabled={sending || !input.trim()} hitSlop={8}>
          <Text style={[styles.send, { color: t.accent, opacity: sending || !input.trim() ? 0.4 : 1 }]}>
            Send
          </Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  list: { padding: 16, gap: 12, flexGrow: 1 },
  empty: { textAlign: "center", marginTop: 80, fontSize: 15, paddingHorizontal: 24 },
  bubble: { borderRadius: 16, paddingVertical: 8, paddingHorizontal: 12, maxWidth: "85%" },
  userBubble: { alignSelf: "flex-end" },
  assistant: { alignSelf: "stretch" },
  error: { paddingHorizontal: 16, paddingBottom: 6, fontSize: 13 },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderTopWidth: 1,
  },
  input: { flex: 1, fontSize: 16, paddingVertical: 8 },
  send: { fontSize: 16, fontWeight: "700" },
});
