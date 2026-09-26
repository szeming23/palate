import { Picker } from "@react-native-picker/picker";
import { useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import {
  Me,
  Memory,
  ModelInfo,
  Profile,
  clearHistory,
  deleteMemory,
  getMe,
  getMemories,
  getModels,
  getProfile,
  saveProfile,
} from "../lib/api";
import { DEFAULT_SETTINGS, Settings, loadSettings, saveSettings } from "../lib/settings";
import { Theme, useTheme } from "../lib/theme";

const EMPTY_PROFILE: Profile = { dietary: "", allergies: "", budget: "", likes: "", dislikes: "", notes: "" };

const PROFILE_FIELDS: { key: keyof Profile; label: string; placeholder: string }[] = [
  { key: "dietary", label: "Dietary needs", placeholder: "e.g. halal, vegetarian, no beef" },
  { key: "allergies", label: "Allergies", placeholder: "e.g. peanuts, shellfish" },
  { key: "budget", label: "Usual budget", placeholder: "e.g. under $10 for lunch" },
  { key: "likes", label: "Likes", placeholder: "e.g. spicy food, noodles, Japanese" },
  { key: "dislikes", label: "Dislikes", placeholder: "e.g. coriander, long queues" },
  { key: "notes", label: "Anything else", placeholder: "e.g. often eat with kids" },
];

export default function SettingsScreen() {
  const t = useTheme();
  const s = makeStyles(t);
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [me, setMe] = useState<Me | null>(null);
  const [profile, setProfile] = useState<Profile>(EMPTY_PROFILE);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [serverStatus, setServerStatus] = useState<string>("");

  useEffect(() => {
    loadSettings().then((loaded) => {
      setSettings(loaded);
      refreshFromServer(loaded);
    });
  }, []);

  async function refreshFromServer(current: Settings) {
    try {
      const [who, m, p, mem] = await Promise.all([getMe(), getModels(), getProfile(), getMemories()]);
      setMe(who);
      setModels(m.models);
      setProfile(p);
      setMemories(mem.memories);
      setServerStatus("");
      // If the saved model isn't allowed for this access code, switch to the server's default.
      if (m.default && !m.models.some((x) => x.id === current.model)) {
        await update("model", m.default, current);
      }
    } catch (e: any) {
      setMe(null);
      setModels([]);
      setServerStatus(e.message);
    }
  }

  async function update<K extends keyof Settings>(key: K, value: Settings[K], base: Settings = settings) {
    const next = { ...base, [key]: value };
    setSettings(next);
    await saveSettings(next);
    return next;
  }

  function usageLine(who: Me) {
    const msgs = who.daily_messages != null ? `${who.today.messages}/${who.daily_messages}` : `${who.today.messages}`;
    const usd =
      who.daily_usd != null
        ? `US$${who.today.cost_usd.toFixed(2)} of US$${who.daily_usd.toFixed(2)}`
        : `US$${who.today.cost_usd.toFixed(2)}`;
    return `Connected as “${who.name}” ✓\nToday: ${msgs} messages, ${usd} used`;
  }

  async function onSaveProfile() {
    try {
      await saveProfile(profile);
      Alert.alert("Saved", "Your preferences are saved.");
    } catch (e: any) {
      Alert.alert("Couldn't save", e.message);
    }
  }

  async function onDeleteMemory(id: number) {
    try {
      await deleteMemory(id);
      setMemories((m) => m.filter((x) => x.id !== id));
    } catch (e: any) {
      Alert.alert("Couldn't delete", e.message);
    }
  }

  function onClearHistory() {
    Alert.alert("Clear chat history?", "Memories and preferences are kept.", [
      { text: "Cancel", style: "cancel" },
      { text: "Clear", style: "destructive", onPress: () => clearHistory().catch(() => {}) },
    ]);
  }

  return (
    <ScrollView style={{ backgroundColor: t.bg }} contentContainerStyle={s.page}>
      <Text style={s.section}>Connection</Text>
      <View style={s.group}>
        <Text style={s.label}>Palate server URL</Text>
        <TextInput
          style={s.input}
          value={settings.backendUrl}
          onChangeText={(v) => update("backendUrl", v.trim())}
          placeholder="http://192.168.1.2:8000"
          placeholderTextColor={t.muted}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
        />
        <Text style={s.label}>Access code</Text>
        <TextInput
          style={s.input}
          value={settings.accessCode}
          onChangeText={(v) => update("accessCode", v.trim())}
          placeholder="plt_..."
          placeholderTextColor={t.muted}
          secureTextEntry
          autoCapitalize="none"
          autoCorrect={false}
        />
        <Pressable style={s.button} onPress={() => refreshFromServer(settings)}>
          <Text style={s.buttonText}>Connect</Text>
        </Pressable>
        {me ? <Text style={s.hint}>{usageLine(me)}</Text> : null}
        {serverStatus ? <Text style={[s.hint, { color: t.bad }]}>{serverStatus}</Text> : null}
      </View>

      <Text style={s.section}>AI model</Text>
      <View style={s.group}>
        {models.length === 0 ? (
          <Text style={s.hint}>Connect to see the models your access code can use.</Text>
        ) : (
          <View style={s.pickerWrap}>
            <Picker
              selectedValue={settings.model}
              onValueChange={(v) => update("model", v)}
              style={{ color: t.text }}
              dropdownIconColor={t.muted}
              mode="dropdown"
            >
              {models.map((m) => (
                <Picker.Item key={m.id} label={m.label} value={m.id} />
              ))}
            </Picker>
          </View>
        )}
        <Text style={s.label}>Your own Claude API key (optional)</Text>
        <TextInput
          style={s.input}
          value={settings.ownApiKey}
          onChangeText={(v) => update("ownApiKey", v.trim())}
          onEndEditing={() => refreshFromServer(settings)}
          placeholder="Leave empty to use the server's key"
          placeholderTextColor={t.muted}
          secureTextEntry
          autoCapitalize="none"
          autoCorrect={false}
        />
        <Text style={s.hint}>
          If set, Palate bills your key instead of the server's and skips the daily budget. It's stored
          encrypted on this phone and never saved on the server.
        </Text>
      </View>

      <Text style={s.section}>Your preferences</Text>
      <View style={s.group}>
        {PROFILE_FIELDS.map((f) => (
          <View key={f.key}>
            <Text style={s.label}>{f.label}</Text>
            <TextInput
              style={s.input}
              value={profile[f.key]}
              onChangeText={(v) => setProfile((p) => ({ ...p, [f.key]: v }))}
              placeholder={f.placeholder}
              placeholderTextColor={t.muted}
            />
          </View>
        ))}
        <Pressable style={s.button} onPress={onSaveProfile}>
          <Text style={s.buttonText}>Save preferences</Text>
        </Pressable>
      </View>

      <Text style={s.section}>What Palate remembers</Text>
      <View style={s.group}>
        {memories.length === 0 ? (
          <Text style={s.hint}>Nothing yet. Palate picks things up as you chat.</Text>
        ) : (
          memories.map((m) => (
            <View key={m.id} style={s.memoryRow}>
              <Text style={[s.body, { flex: 1 }]}>
                {m.kind === "location" ? "📍 " : ""}
                {m.content}
              </Text>
              <Pressable onPress={() => onDeleteMemory(m.id)} hitSlop={8}>
                <Text style={{ color: t.bad, fontWeight: "600" }}>Forget</Text>
              </Pressable>
            </View>
          ))
        )}
      </View>

      <Pressable onPress={onClearHistory} style={{ alignSelf: "center", padding: 12 }}>
        <Text style={{ color: t.bad, fontWeight: "600" }}>Clear chat history</Text>
      </Pressable>
    </ScrollView>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    page: { padding: 16, paddingBottom: 48 },
    section: { color: t.muted, fontSize: 13, fontWeight: "700", textTransform: "uppercase", marginTop: 20, marginBottom: 8 },
    group: { backgroundColor: t.surface, borderColor: t.border, borderWidth: 1, borderRadius: 14, padding: 14, gap: 6 },
    label: { color: t.text, fontSize: 14, fontWeight: "600", marginTop: 6 },
    body: { color: t.text, fontSize: 15 },
    hint: { color: t.muted, fontSize: 13, marginTop: 4 },
    input: { color: t.text, borderColor: t.border, borderWidth: 1, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 15 },
    pickerWrap: { borderColor: t.border, borderWidth: 1, borderRadius: 10, overflow: "hidden" },
    button: { backgroundColor: t.accent, borderRadius: 10, paddingVertical: 12, alignItems: "center", marginTop: 10 },
    buttonText: { color: t.accentText, fontWeight: "700", fontSize: 15 },
    memoryRow: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 6 },
  });
}
