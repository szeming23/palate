import { useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";

import { PlaceCard as Card, sendFeedback } from "../lib/api";
import { useTheme } from "../lib/theme";

function formatDistance(m?: number) {
  if (m == null) return null;
  return m < 1000 ? `${m} m` : `${(m / 1000).toFixed(1)} km`;
}

export default function PlaceCard({ card }: { card: Card }) {
  const t = useTheme();
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);

  const meta = [
    card.rating != null ? `★ ${card.rating}${card.rating_count ? ` (${card.rating_count})` : ""}` : null,
    card.price,
    formatDistance(card.distance_m),
    card.open_now == null ? null : card.open_now ? "Open now" : "Closed",
  ].filter(Boolean);

  async function vote(v: "up" | "down") {
    const next = feedback === v ? null : v;
    setFeedback(next);
    try {
      await sendFeedback(card.recommendation_id, next);
    } catch {
      setFeedback(feedback); // revert on failure
    }
  }

  return (
    <View style={[styles.card, { backgroundColor: t.surface, borderColor: t.border }]}>
      <Text style={[styles.name, { color: t.text }]}>{card.name}</Text>
      {card.type ? <Text style={[styles.small, { color: t.muted }]}>{card.type}</Text> : null}
      <Text style={[styles.small, { color: t.muted }]}>{meta.join("  ·  ")}</Text>
      <Text style={[styles.reason, { color: t.text }]}>{card.reason}</Text>
      {card.address ? (
        <Text style={[styles.small, { color: t.muted }]} numberOfLines={2}>
          {card.address}
        </Text>
      ) : null}
      <View style={styles.actions}>
        {card.maps_url ? (
          <Pressable onPress={() => Linking.openURL(card.maps_url!)} hitSlop={8}>
            <Text style={[styles.link, { color: t.accent }]}>Open in Maps</Text>
          </Pressable>
        ) : (
          <View />
        )}
        <View style={styles.votes}>
          <Pressable onPress={() => vote("up")} hitSlop={8} accessibilityLabel="Good pick">
            <Text style={[styles.vote, { opacity: feedback === "up" ? 1 : 0.4 }]}>👍</Text>
          </Pressable>
          <Pressable onPress={() => vote("down")} hitSlop={8} accessibilityLabel="Bad pick">
            <Text style={[styles.vote, { opacity: feedback === "down" ? 1 : 0.4 }]}>👎</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderWidth: 1, borderRadius: 14, padding: 12, marginTop: 8, gap: 3 },
  name: { fontSize: 16, fontWeight: "600" },
  small: { fontSize: 13 },
  reason: { fontSize: 14, marginVertical: 4 },
  actions: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 6 },
  link: { fontSize: 14, fontWeight: "600" },
  votes: { flexDirection: "row", gap: 16 },
  vote: { fontSize: 20 },
});
