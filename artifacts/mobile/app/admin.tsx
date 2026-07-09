import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Platform,
  Clipboard,
  Alert,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons, MaterialCommunityIcons, Feather } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import Animated, { FadeInDown, FadeIn } from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { router } from 'expo-router';

// ─── Config ────────────────────────────────────────────────────────────────
// Admin password — app ထဲမှာ ပြောင်းနိုင်သည်
const ADMIN_PASSWORD = 'STAR2026';
const STORAGE_KEY = 'admin_generated_keys';

// ─── Helpers ───────────────────────────────────────────────────────────────
function randomSuffix(len = 4): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // ambiguous chars removed
  let s = '';
  for (let i = 0; i < len; i++) {
    s += chars[Math.floor(Math.random() * chars.length)];
  }
  return s;
}

function formatDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}${m}${day}`;
}

function displayDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}/${m}/${day}`;
}

function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

function makeKey(expiryDate: Date, suffix?: string): string {
  return `STAR-${formatDate(expiryDate)}-${suffix ?? randomSuffix()}`;
}

interface SavedKey {
  key: string;
  expiry: string;
  createdAt: string;
  note: string;
}

// ─── Copy to clipboard ─────────────────────────────────────────────────────
function copyToClipboard(text: string) {
  try {
    Clipboard.setString(text);
  } catch {}
  Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
}

// ─── Admin Screen ──────────────────────────────────────────────────────────
export default function AdminScreen() {
  const insets = useSafeAreaInsets();
  const isWeb = Platform.OS === 'web';
  const topPad = isWeb ? 67 : insets.top;
  const botPad = isWeb ? 34 : insets.bottom;

  const [authed, setAuthed] = useState(false);
  const [pwInput, setPwInput] = useState('');
  const [pwError, setPwError] = useState('');

  // Key generator state
  const [expiryDays, setExpiryDays] = useState('30');
  const [customSuffix, setCustomSuffix] = useState('');
  const [count, setCount] = useState('1');
  const [note, setNote] = useState('');
  const [lastGenerated, setLastGenerated] = useState<SavedKey[]>([]);
  const [history, setHistory] = useState<SavedKey[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [showSettings, setShowSettings] = useState(false);

  // Load history on mount
  React.useEffect(() => {
    if (authed) loadHistory();
  }, [authed]);

  async function loadHistory() {
    try {
      const raw = await AsyncStorage.getItem(STORAGE_KEY);
      if (raw) setHistory(JSON.parse(raw));
    } catch {}
  }

  async function saveHistory(keys: SavedKey[]) {
    const updated = [...keys, ...history].slice(0, 200); // keep last 200
    setHistory(updated);
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  }

  function login() {
    if (pwInput === ADMIN_PASSWORD) {
      setAuthed(true);
      setPwError('');
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } else {
      setPwError('Password မမှန်ပါ');
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    }
  }

  function generateKeys() {
    const days = parseInt(expiryDays, 10);
    const n = Math.min(Math.max(parseInt(count, 10) || 1, 1), 20);
    if (isNaN(days) || days < 1) {
      Alert.alert('Error', 'Expiry days မမှန်ပါ');
      return;
    }
    const expiry = addDays(new Date(), days);
    const generated: SavedKey[] = [];
    for (let i = 0; i < n; i++) {
      const suffix = customSuffix.trim().toUpperCase() || randomSuffix();
      const key = makeKey(expiry, n > 1 ? randomSuffix() : suffix);
      generated.push({
        key,
        expiry: displayDate(expiry),
        createdAt: displayDate(new Date()),
        note: note.trim(),
      });
    }
    setLastGenerated(generated);
    saveHistory(generated);
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
  }

  function copyAll() {
    const text = lastGenerated.map((k) => k.key).join('\n');
    copyToClipboard(text);
    Alert.alert('Copied', `Key ${lastGenerated.length} ခု ကော်ပီကူးပြီး`);
  }

  // ── Login screen ──────────────────────────────────────────────────────
  if (!authed) {
    return (
      <LinearGradient colors={['#040810', '#070b14', '#040810']} style={{ flex: 1 }}>
        <View style={[styles.loginContainer, { paddingTop: topPad + 40, paddingBottom: botPad }]}>
          <Animated.View entering={FadeIn.duration(500)}>
            <View style={styles.lockIcon}>
              <MaterialCommunityIcons name="shield-key" size={48} color="#00b4ff" />
            </View>
            <Text style={styles.loginTitle}>Admin Panel</Text>
            <Text style={styles.loginSub}>Password ထည့်ပါ</Text>

            <View style={[styles.inputWrap, { marginTop: 24, marginBottom: 12 }]}>
              <Ionicons name="lock-closed-outline" size={18} color="#4a6b8a" style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                placeholder="Admin Password"
                placeholderTextColor="#4a6b8a"
                value={pwInput}
                onChangeText={setPwInput}
                secureTextEntry
                autoCapitalize="none"
                onSubmitEditing={login}
              />
            </View>

            {pwError ? (
              <Text style={styles.errorText}>{pwError}</Text>
            ) : null}

            <TouchableOpacity style={styles.loginBtn} onPress={login} activeOpacity={0.8}>
              <LinearGradient
                colors={['#00b4ff', '#0080cc']}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 0 }}
                style={styles.loginBtnGrad}
              >
                <Text style={styles.loginBtnText}>ဝင်ရောက်ပါ</Text>
              </LinearGradient>
            </TouchableOpacity>

            <TouchableOpacity onPress={() => router.back()} style={styles.backLink} activeOpacity={0.7}>
              <Feather name="arrow-left" size={14} color="#4a6b8a" />
              <Text style={styles.backLinkText}>ပြန်သွားပါ</Text>
            </TouchableOpacity>
          </Animated.View>
        </View>
      </LinearGradient>
    );
  }

  // ── Admin dashboard ───────────────────────────────────────────────────
  return (
    <LinearGradient colors={['#040810', '#070b14', '#040810']} style={{ flex: 1 }}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={[
          styles.container,
          { paddingTop: topPad + 16, paddingBottom: botPad + 32 },
        ]}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <Animated.View entering={FadeIn.duration(500)} style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} activeOpacity={0.7} style={styles.backBtn}>
            <Feather name="arrow-left" size={20} color="#4a6b8a" />
          </TouchableOpacity>
          <View style={styles.headerCenter}>
            <MaterialCommunityIcons name="shield-key" size={22} color="#00b4ff" />
            <Text style={styles.headerTitle}>Admin Key Generator</Text>
          </View>
          <TouchableOpacity onPress={() => setShowSettings((v) => !v)} activeOpacity={0.7}>
            <Feather name="settings" size={20} color="#4a6b8a" />
          </TouchableOpacity>
        </Animated.View>

        {/* Settings (password change) */}
        {showSettings ? (
          <Animated.View entering={FadeInDown.duration(300)} style={styles.card}>
            <Text style={styles.cardTitle}>Password ပြောင်း</Text>
            <View style={[styles.inputWrap, { marginTop: 10 }]}>
              <Ionicons name="lock-closed-outline" size={16} color="#4a6b8a" style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                placeholder="New Password"
                placeholderTextColor="#4a6b8a"
                value={newPassword}
                onChangeText={setNewPassword}
                secureTextEntry
                autoCapitalize="none"
              />
            </View>
            <TouchableOpacity
              style={[styles.smallBtn, { marginTop: 10 }]}
              onPress={() => {
                if (newPassword.length < 4) { Alert.alert('Error', 'Password အနည်းဆုံး ၄ လုံး'); return; }
                Alert.alert('Note', 'Password ပြောင်းမှု app restart မှ ရှင်းသွားမည်။ Code ထဲ ADMIN_PASSWORD ကို ပြောင်းရမည်။');
              }}
              activeOpacity={0.75}
            >
              <Text style={styles.smallBtnText}>ပြောင်းပါ</Text>
            </TouchableOpacity>
          </Animated.View>
        ) : null}

        {/* Key Generator */}
        <Animated.View entering={FadeInDown.delay(100).duration(500)} style={styles.card}>
          <View style={styles.cardHeader}>
            <MaterialCommunityIcons name="key-plus" size={18} color="#00b4ff" />
            <Text style={styles.cardTitle}>Key ဖန်တီး</Text>
          </View>

          {/* Expiry quick select */}
          <Text style={styles.label}>သက်တမ်း (ရက်အရေအတွက်)</Text>
          <View style={styles.quickRow}>
            {['7', '14', '30', '60', '90'].map((d) => (
              <TouchableOpacity
                key={d}
                style={[styles.quickChip, expiryDays === d && styles.quickChipActive]}
                onPress={() => setExpiryDays(d)}
                activeOpacity={0.75}
              >
                <Text style={[styles.quickChipText, expiryDays === d && styles.quickChipTextActive]}>
                  {d}ရက်
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          <View style={styles.inputWrap}>
            <Feather name="calendar" size={16} color="#4a6b8a" style={styles.inputIcon} />
            <TextInput
              style={styles.input}
              placeholder="ရက်အရေအတွက် (ကိုယ်တိုင်ရိုက်)"
              placeholderTextColor="#4a6b8a"
              value={expiryDays}
              onChangeText={setExpiryDays}
              keyboardType="number-pad"
            />
          </View>

          {/* Expiry preview */}
          {expiryDays && !isNaN(parseInt(expiryDays)) ? (
            <View style={styles.previewRow}>
              <Feather name="clock" size={12} color="#4a6b8a" />
              <Text style={styles.previewText}>
                သက်တမ်း: {displayDate(addDays(new Date(), parseInt(expiryDays)))} အထိ
              </Text>
            </View>
          ) : null}

          {/* Count */}
          <Text style={[styles.label, { marginTop: 14 }]}>Key အရေအတွက် (max 20)</Text>
          <View style={styles.quickRow}>
            {['1', '3', '5', '10'].map((n) => (
              <TouchableOpacity
                key={n}
                style={[styles.quickChip, count === n && styles.quickChipActive]}
                onPress={() => setCount(n)}
                activeOpacity={0.75}
              >
                <Text style={[styles.quickChipText, count === n && styles.quickChipTextActive]}>
                  {n}ခု
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Custom suffix (optional, single key only) */}
          <Text style={[styles.label, { marginTop: 14 }]}>
            Suffix (optional) — ၁ ခုသာ ဖန်တီးလျှင် သုံးနိုင်
          </Text>
          <View style={styles.inputWrap}>
            <MaterialCommunityIcons name="key-variant" size={16} color="#4a6b8a" style={styles.inputIcon} />
            <TextInput
              style={styles.input}
              placeholder="ဥပမာ: VIP1 (ထားရင် auto)"
              placeholderTextColor="#4a6b8a"
              value={customSuffix}
              onChangeText={setCustomSuffix}
              autoCapitalize="characters"
              maxLength={8}
            />
          </View>

          {/* Note */}
          <Text style={[styles.label, { marginTop: 14 }]}>Note (optional)</Text>
          <View style={styles.inputWrap}>
            <Feather name="edit-3" size={16} color="#4a6b8a" style={styles.inputIcon} />
            <TextInput
              style={styles.input}
              placeholder="ဥပမာ: User နာမည်"
              placeholderTextColor="#4a6b8a"
              value={note}
              onChangeText={setNote}
            />
          </View>

          {/* Generate button */}
          <TouchableOpacity style={styles.generateBtn} onPress={generateKeys} activeOpacity={0.8}>
            <LinearGradient
              colors={['#00b4ff', '#0080cc']}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
              style={styles.generateBtnGrad}
            >
              <MaterialCommunityIcons name="key-plus" size={20} color="#000" />
              <Text style={styles.generateBtnText}>Key ဖန်တီးမည်</Text>
            </LinearGradient>
          </TouchableOpacity>
        </Animated.View>

        {/* Generated keys */}
        {lastGenerated.length > 0 ? (
          <Animated.View entering={FadeInDown.duration(400)} style={styles.card}>
            <View style={styles.cardHeader}>
              <MaterialCommunityIcons name="key-chain" size={18} color="#00e676" />
              <Text style={[styles.cardTitle, { color: '#00e676' }]}>
                ဖန်တီးပြီး Key ({lastGenerated.length} ခု)
              </Text>
              {lastGenerated.length > 1 ? (
                <TouchableOpacity onPress={copyAll} activeOpacity={0.75} style={styles.copyAllBtn}>
                  <Feather name="copy" size={14} color="#00b4ff" />
                  <Text style={styles.copyAllText}>အားလုံး Copy</Text>
                </TouchableOpacity>
              ) : null}
            </View>

            {lastGenerated.map((item, i) => (
              <View key={i} style={styles.keyRow}>
                <View style={styles.keyInfo}>
                  <Text style={styles.keyText}>{item.key}</Text>
                  <Text style={styles.keyMeta}>
                    သက်တမ်း: {item.expiry}
                    {item.note ? ` | ${item.note}` : ''}
                  </Text>
                </View>
                <TouchableOpacity
                  onPress={() => {
                    copyToClipboard(item.key);
                    Alert.alert('Copied!', item.key);
                  }}
                  activeOpacity={0.75}
                  style={styles.copyBtn}
                >
                  <Feather name="copy" size={16} color="#00b4ff" />
                </TouchableOpacity>
              </View>
            ))}
          </Animated.View>
        ) : null}

        {/* History */}
        <Animated.View entering={FadeInDown.delay(200).duration(500)} style={styles.card}>
          <TouchableOpacity
            style={styles.cardHeader}
            onPress={() => setShowHistory((v) => !v)}
            activeOpacity={0.75}
          >
            <MaterialCommunityIcons name="history" size={18} color="#4a6b8a" />
            <Text style={[styles.cardTitle, { color: '#a0c4e8' }]}>
              ယခင် ဖန်တီးထားသော Key ({history.length})
            </Text>
            <Feather name={showHistory ? 'chevron-up' : 'chevron-down'} size={16} color="#4a6b8a" />
          </TouchableOpacity>

          {showHistory && history.length === 0 ? (
            <Text style={styles.emptyText}>Key မဖန်တီးရသေးပါ</Text>
          ) : null}

          {showHistory
            ? history.slice(0, 50).map((item, i) => (
                <View key={i} style={[styles.keyRow, { borderTopWidth: i === 0 ? 0 : 1, borderTopColor: '#152040' }]}>
                  <View style={styles.keyInfo}>
                    <Text style={styles.keyText}>{item.key}</Text>
                    <Text style={styles.keyMeta}>
                      {item.createdAt} ဖန်တီး | {item.expiry} ကုန်
                      {item.note ? ` | ${item.note}` : ''}
                    </Text>
                  </View>
                  <TouchableOpacity
                    onPress={() => copyToClipboard(item.key)}
                    activeOpacity={0.75}
                    style={styles.copyBtn}
                  >
                    <Feather name="copy" size={14} color="#4a6b8a" />
                  </TouchableOpacity>
                </View>
              ))
            : null}

          {showHistory && history.length > 50 ? (
            <Text style={[styles.emptyText, { textAlign: 'center' }]}>
              + {history.length - 50} ခု ထပ်ရှိသည်
            </Text>
          ) : null}
        </Animated.View>

        {/* Guide */}
        <Animated.View entering={FadeInDown.delay(300).duration(500)} style={[styles.card, { borderColor: '#00b4ff33' }]}>
          <View style={styles.cardHeader}>
            <Feather name="info" size={16} color="#00b4ff" />
            <Text style={[styles.cardTitle, { color: '#a0c4e8' }]}>Key Format လမ်းညွှန်</Text>
          </View>
          <Text style={styles.guideText}>
            {'Format:  STAR-YYYYMMDD-XXXX\n\n'}
            {'STAR     ← prefix (မပြောင်းပါနှင့်)\n'}
            {'YYYYMMDD ← ကုန်မည့်ရက် (ဥပမာ: 20260731)\n'}
            {'XXXX     ← suffix (A-Z, 0-9, 1-8  လုံး)\n\n'}
            {'ဥပမာ: STAR-20260731-VIP1\n'}
            {'        STAR-20261231-AB99\n\n'}
            {'Key ကို app ထဲ type ရင် auto validate.\n'}
            {'Network မလိုဘဲ locally စစ်ဆေးသည်။'}
          </Text>
        </Animated.View>
      </ScrollView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  loginContainer: {
    flex: 1,
    paddingHorizontal: 32,
    justifyContent: 'flex-start',
  },
  lockIcon: {
    alignSelf: 'center',
    marginBottom: 16,
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#0d1728',
    borderWidth: 1,
    borderColor: '#152040',
    alignItems: 'center',
    justifyContent: 'center',
  },
  loginTitle: {
    fontSize: 24,
    fontFamily: 'Inter_700Bold',
    color: '#e0f0ff',
    textAlign: 'center',
  },
  loginSub: {
    fontSize: 13,
    fontFamily: 'Inter_400Regular',
    color: '#4a6b8a',
    textAlign: 'center',
    marginTop: 6,
  },
  errorText: {
    fontSize: 13,
    fontFamily: 'Inter_500Medium',
    color: '#ff4444',
    textAlign: 'center',
    marginBottom: 8,
  },
  loginBtn: {
    borderRadius: 12,
    overflow: 'hidden',
    marginTop: 4,
  },
  loginBtnGrad: {
    height: 50,
    alignItems: 'center',
    justifyContent: 'center',
  },
  loginBtnText: {
    fontSize: 16,
    fontFamily: 'Inter_700Bold',
    color: '#000',
  },
  backLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    justifyContent: 'center',
    marginTop: 20,
  },
  backLinkText: {
    fontSize: 13,
    fontFamily: 'Inter_500Medium',
    color: '#4a6b8a',
  },
  container: {
    paddingHorizontal: 20,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
  },
  backBtn: {
    padding: 4,
  },
  headerCenter: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  headerTitle: {
    fontSize: 16,
    fontFamily: 'Inter_700Bold',
    color: '#e0f0ff',
  },
  card: {
    backgroundColor: '#0d1728',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#152040',
    padding: 18,
    marginBottom: 14,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 14,
  },
  cardTitle: {
    fontSize: 15,
    fontFamily: 'Inter_600SemiBold',
    color: '#e0f0ff',
    flex: 1,
  },
  label: {
    fontSize: 12,
    fontFamily: 'Inter_500Medium',
    color: '#4a6b8a',
    marginBottom: 8,
  },
  quickRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 10,
  },
  quickChip: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#152040',
    backgroundColor: '#070b14',
  },
  quickChipActive: {
    borderColor: '#00b4ff',
    backgroundColor: '#00b4ff22',
  },
  quickChipText: {
    fontSize: 13,
    fontFamily: 'Inter_500Medium',
    color: '#4a6b8a',
  },
  quickChipTextActive: {
    color: '#00b4ff',
  },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#070b14',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#152040',
    paddingHorizontal: 12,
    height: 44,
  },
  inputIcon: {
    marginRight: 8,
  },
  input: {
    flex: 1,
    fontSize: 14,
    fontFamily: 'Inter_400Regular',
    color: '#e0f0ff',
    height: 44,
  },
  previewRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 6,
  },
  previewText: {
    fontSize: 12,
    fontFamily: 'Inter_400Regular',
    color: '#4a6b8a',
  },
  generateBtn: {
    borderRadius: 12,
    overflow: 'hidden',
    marginTop: 18,
  },
  generateBtnGrad: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    height: 52,
  },
  generateBtnText: {
    fontSize: 16,
    fontFamily: 'Inter_700Bold',
    color: '#000',
  },
  keyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    gap: 10,
  },
  keyInfo: {
    flex: 1,
    gap: 3,
  },
  keyText: {
    fontSize: 14,
    fontFamily: 'Inter_600SemiBold',
    color: '#00b4ff',
    letterSpacing: 0.5,
  },
  keyMeta: {
    fontSize: 11,
    fontFamily: 'Inter_400Regular',
    color: '#4a6b8a',
  },
  copyBtn: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: '#070b14',
    borderWidth: 1,
    borderColor: '#152040',
    alignItems: 'center',
    justifyContent: 'center',
  },
  copyAllBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  copyAllText: {
    fontSize: 12,
    fontFamily: 'Inter_500Medium',
    color: '#00b4ff',
  },
  emptyText: {
    fontSize: 13,
    fontFamily: 'Inter_400Regular',
    color: '#4a6b8a',
    paddingVertical: 8,
  },
  guideText: {
    fontSize: 13,
    fontFamily: 'Inter_400Regular',
    color: '#a0c4e8',
    lineHeight: 20,
  },
  smallBtn: {
    height: 38,
    borderRadius: 10,
    backgroundColor: '#00b4ff22',
    borderWidth: 1,
    borderColor: '#00b4ff',
    alignItems: 'center',
    justifyContent: 'center',
  },
  smallBtnText: {
    fontSize: 13,
    fontFamily: 'Inter_600SemiBold',
    color: '#00b4ff',
  },
});
