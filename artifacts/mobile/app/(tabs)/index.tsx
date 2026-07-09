import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Platform,
  Linking,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import {
  Ionicons,
  MaterialCommunityIcons,
  Feather,
  FontAwesome5,
} from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Haptics from 'expo-haptics';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withTiming,
  Easing,
  FadeInDown,
  FadeIn,
} from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';
import { WebView } from 'react-native-webview';
import { router } from 'expo-router';

// ─── Portal URL Template ───────────────────────────────────────────────────
// mac, gw_address, nasip, ip ကို auto-detected values နဲ့ replace မည်
const PORTAL_URL_TEMPLATE =
  'https://portal-as.ruijienetworks.com/api/auth/wifidog?stage=portal&gw_id=984a6b458027&gw_sn=H1T078800132C&gw_address=192.168.110.1&gw_port=2060&ip=192.168.110.142&mac=ca:51:aa:ff:b8:51&slot_num=33&nasip=192.168.1.161&ssid=VLAN233&ustate=0&mac_req=1&url=http%3A%2F%2F192.168.0.1%2F&chap_id=%5C016&chap_challenge=%5C135%5C061%5C367%5C376%5C225%5C324%5C217%5C041%5C213%5C145%5C002%5C251%5C074%5C104%5C267%5C152';

// Captive portal detection URLs (try in order)
const DETECT_URLS = [
  'http://connectivitycheck.gstatic.com/generate_204',
  'http://clients3.google.com/generate_204',
  'http://www.google.com/generate_204',
  'http://connectivitycheck.android.com/generate_204',
];

// Build final portal URL by replacing network params
function buildPortalUrl(mac: string, gw: string, ip: string): string {
  try {
    const url = new URL(PORTAL_URL_TEMPLATE);
    if (mac) url.searchParams.set('mac', mac);
    if (gw) {
      url.searchParams.set('gw_address', gw);
      url.searchParams.set('nasip', gw);
    }
    if (ip) url.searchParams.set('ip', ip);
    return url.toString();
  } catch {
    return PORTAL_URL_TEMPLATE;
  }
}

// Parse MAC / gateway / IP from a Ruijie redirect URL
function parsePortalRedirect(url: string): {
  mac?: string;
  gw?: string;
  ip?: string;
} {
  try {
    const u = new URL(url);
    return {
      mac:
        u.searchParams.get('mac') ??
        u.searchParams.get('umac') ??
        u.searchParams.get('client_mac') ??
        undefined,
      gw:
        u.searchParams.get('gw_address') ??
        u.searchParams.get('gateway') ??
        u.searchParams.get('nasip') ??
        undefined,
      ip:
        u.searchParams.get('ip') ??
        u.searchParams.get('client_ip') ??
        undefined,
    };
  } catch {
    return {};
  }
}

// ─── Date-Encoded Key Validation ──────────────────────────────────────────
// Format: STAR-YYYYMMDD-XXXX  (ဥပမာ: STAR-20260731-AB12)
type KeyResult = {
  valid: boolean;
  message: string;
  daysLeft?: number;
};

function validateKey(raw: string): KeyResult {
  const key = raw.trim().toUpperCase();
  const parts = key.split('-');

  // Format: STAR-YYYYMMDD-XXXX (exactly 3 dash-separated parts)
  if (parts.length !== 3 || parts[0] !== 'STAR') {
    return { valid: false, message: 'Format မမှန်ပါ → STAR-YYYYMMDD-XXXX' };
  }

  const datePart = parts[1];
  const suffix = parts[2];

  // Validate date part: exactly 8 digits
  if (!/^\d{8}$/.test(datePart)) {
    return { valid: false, message: 'Date part မမှန်ပါ (YYYYMMDD ဖြစ်ရမည်)' };
  }

  // Validate suffix: 1-8 alphanumeric chars
  if (!/^[A-Z0-9]{1,8}$/.test(suffix)) {
    return { valid: false, message: 'Suffix မမှန်ပါ (A-Z, 0-9 သာ)' };
  }

  const y = parseInt(datePart.slice(0, 4), 10);
  const m = parseInt(datePart.slice(4, 6), 10) - 1; // 0-indexed
  const d = parseInt(datePart.slice(6, 8), 10);

  // Calendar round-trip check: reconstructed date must match input
  const expiryDate = new Date(y, m, d, 23, 59, 59);
  if (
    isNaN(expiryDate.getTime()) ||
    expiryDate.getFullYear() !== y ||
    expiryDate.getMonth() !== m ||
    expiryDate.getDate() !== d
  ) {
    return { valid: false, message: 'Date မမှန်ကန်ပါ' };
  }

  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const expiryDay = new Date(y, m, d);
  const daysLeft = Math.ceil(
    (expiryDay.getTime() - todayStart.getTime()) / 86_400_000
  );
  const expiryStr = `${y}/${String(m + 1).padStart(2, '0')}/${String(d).padStart(2, '0')}`;

  if (daysLeft < 0) {
    return { valid: false, message: `သက်တမ်းကုန်ပြီ (${expiryStr})` };
  }
  if (daysLeft === 0) {
    return { valid: true, message: `ဒီနေ့ ကုန်မည် — ${expiryStr}`, daysLeft: 0 };
  }
  return {
    valid: true,
    message: `${daysLeft} ရက် ကျန် — ${expiryStr} အထိ`,
    daysLeft,
  };
}

// ─── Glow Dot ──────────────────────────────────────────────────────────────
function GlowDot({ color }: { color: string }) {
  const opacity = useSharedValue(0.3);
  useEffect(() => {
    opacity.value = withRepeat(
      withTiming(1, { duration: 800, easing: Easing.inOut(Easing.ease) }),
      -1,
      true
    );
  }, []);
  const style = useAnimatedStyle(() => ({ opacity: opacity.value }));
  return (
    <Animated.View
      style={[{ width: 8, height: 8, borderRadius: 4, backgroundColor: color }, style]}
    />
  );
}

// ─── Small helpers ─────────────────────────────────────────────────────────
function NetRow({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <View style={styles.netRow}>
      <MaterialCommunityIcons name={icon as any} size={14} color="#4a6b8a" />
      <Text style={styles.netLabel}>{label}</Text>
      <Text style={styles.netValue} numberOfLines={1} ellipsizeMode="middle">
        {value}
      </Text>
    </View>
  );
}

function ManualField({
  icon,
  placeholder,
  value,
  onChange,
}: {
  icon: string;
  placeholder: string;
  value: string;
  onChange: (t: string) => void;
}) {
  return (
    <View style={styles.inputWrap}>
      <MaterialCommunityIcons
        name={icon as any}
        size={16}
        color="#4a6b8a"
        style={styles.inputIcon}
      />
      <TextInput
        style={styles.input}
        placeholder={placeholder}
        placeholderTextColor="#4a6b8a"
        value={value}
        onChangeText={onChange}
        autoCapitalize="none"
        autoCorrect={false}
      />
    </View>
  );
}

// ─── Main Screen ───────────────────────────────────────────────────────────
type KeyStatus = 'idle' | 'valid' | 'invalid';
type DetectStatus = 'idle' | 'detecting' | 'found' | 'failed';

export default function HomeScreen() {
  const insets = useSafeAreaInsets();
  const isWeb = Platform.OS === 'web';
  const topPad = isWeb ? 67 : insets.top;
  const botPad = isWeb ? 34 : insets.bottom;

  // ── Key state ──
  const [keyInput, setKeyInput] = useState('');
  const [keyStatus, setKeyStatus] = useState<KeyStatus>('idle');
  const [keyResult, setKeyResult] = useState<KeyResult | null>(null);

  // ── Network detect state ──
  const [detectStatus, setDetectStatus] = useState<DetectStatus>('idle');
  const [macAddr, setMacAddr] = useState('');
  const [gatewayIp, setGatewayIp] = useState('');
  const [deviceIp, setDeviceIp] = useState('');

  // ── Manual fallback ──
  const [showManual, setShowManual] = useState(false);
  const [manualMac, setManualMac] = useState('');
  const [manualGw, setManualGw] = useState('');
  const [manualIp, setManualIp] = useState('');

  // ── WebView detection ──
  const [webViewUrl, setWebViewUrl] = useState<string | null>(null);
  const [webViewKey, setWebViewKey] = useState(0);
  const urlIndexRef = useRef(0);

  // ── Secret admin tap ──
  const adminTapCount = useRef(0);
  const adminTapTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleLogoTap() {
    adminTapCount.current += 1;
    if (adminTapTimer.current) clearTimeout(adminTapTimer.current);
    if (adminTapCount.current >= 5) {
      adminTapCount.current = 0;
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      router.push('/admin');
    } else {
      adminTapTimer.current = setTimeout(() => {
        adminTapCount.current = 0;
      }, 2000);
    }
  }

  // ── Animations ──
  const pulseAnim = useSharedValue(1);
  useEffect(() => {
    pulseAnim.value = withRepeat(
      withTiming(1.04, { duration: 1200, easing: Easing.inOut(Easing.ease) }),
      -1,
      true
    );
    loadSavedKey();
  }, []);

  const logoStyle = useAnimatedStyle(() => ({
    transform: [{ scale: pulseAnim.value }],
  }));

  // ── Persist key ──
  async function loadSavedKey() {
    try {
      const saved = await AsyncStorage.getItem('star_key');
      if (saved) {
        const result = validateKey(saved);
        if (result.valid) {
          setKeyInput(saved);
          setKeyStatus('valid');
          setKeyResult(result);
        }
      }
    } catch {}
  }

  // ── Key check (local, no network) ──
  function checkKey() {
    const result = validateKey(keyInput);
    setKeyResult(result);
    if (result.valid) {
      setKeyStatus('valid');
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      AsyncStorage.setItem('star_key', keyInput.trim().toUpperCase()).catch(() => {});
    } else {
      setKeyStatus('invalid');
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    }
  }

  function resetKey() {
    setKeyInput('');
    setKeyStatus('idle');
    setKeyResult(null);
    AsyncStorage.removeItem('star_key').catch(() => {});
  }

  // ── Network detection ──
  function startDetect() {
    setDetectStatus('detecting');
    setMacAddr('');
    setGatewayIp('');
    setDeviceIp('');
    urlIndexRef.current = 0;
    Haptics.selectionAsync();

    if (Platform.OS === 'web') {
      // Web fallback: fetch + redirect:manual
      detectViaFetch();
    } else {
      // Native: hidden WebView intercepts Ruijie captive portal redirect
      setWebViewUrl(DETECT_URLS[0]);
      setWebViewKey((k) => k + 1);
    }
  }

  async function detectViaFetch() {
    for (const url of DETECT_URLS) {
      try {
        const ctrl = new AbortController();
        const t = setTimeout(() => ctrl.abort(), 4000);
        const res = await fetch(url, {
          method: 'GET',
          redirect: 'manual',
          signal: ctrl.signal,
        });
        clearTimeout(t);
        const loc =
          res.headers.get('location') || res.headers.get('Location') || '';
        if (loc) {
          const parsed = parsePortalRedirect(loc);
          if (parsed.mac || parsed.gw) {
            applyDetected(parsed.mac, parsed.gw, parsed.ip);
            return;
          }
        }
      } catch {}
    }
    onDetectFailed();
  }

  function applyDetected(mac?: string, gw?: string, ip?: string) {
    if (mac) setMacAddr(mac);
    if (gw) setGatewayIp(gw);
    if (ip) setDeviceIp(ip);
    setDetectStatus('found');
    setWebViewUrl(null);
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
  }

  function onDetectFailed() {
    setDetectStatus('failed');
    setShowManual(true);
    setWebViewUrl(null);
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
  }

  function tryNextUrl() {
    const next = urlIndexRef.current + 1;
    if (next < DETECT_URLS.length) {
      urlIndexRef.current = next;
      setWebViewUrl(DETECT_URLS[next]);
      setWebViewKey((k) => k + 1);
    } else {
      onDetectFailed();
    }
  }

  // Called for every URL the WebView is about to load
  function handleWebViewRequest(url: string): boolean {
    if (!url || url === 'about:blank') return true;

    const isDetectUrl = DETECT_URLS.some((u) => url.startsWith(u.split('/generate_')[0]));
    if (isDetectUrl) return true; // Allow the check URL itself

    // Any other URL = Ruijie portal redirect → parse & block navigation
    const parsed = parsePortalRedirect(url);
    if (parsed.mac || parsed.gw || parsed.ip) {
      applyDetected(parsed.mac, parsed.gw, parsed.ip);
    } else {
      // Redirected somewhere unexpected — not a Ruijie portal, try next URL
      tryNextUrl();
    }
    return false; // Block WebView from navigating to the portal
  }

  // ── Open portal ──
  function openPortal() {
    const mac = macAddr || manualMac;
    const gw = gatewayIp || manualGw;
    const ip = deviceIp || manualIp;
    if (!mac || !gw) {
      Alert.alert('Error', 'MAC Address နှင့် Gateway IP လိုအပ်သည်');
      return;
    }
    const url = buildPortalUrl(mac, gw, ip);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
    Linking.openURL(url).catch(() =>
      Alert.alert('Error', 'Browser ဖွင့်၍ မရပါ')
    );
  }

  const effectiveMac = macAddr || manualMac;
  const effectiveGw = gatewayIp || manualGw;
  const effectiveIp = deviceIp || manualIp;
  const canOpenPortal = keyStatus === 'valid' && !!effectiveMac && !!effectiveGw;

  return (
    <LinearGradient colors={['#040810', '#070b14', '#040810']} style={{ flex: 1 }}>
      {/* ── Hidden WebView for captive portal detection ── */}
      {Platform.OS !== 'web' && webViewUrl ? (
        <View style={styles.hiddenWebView}>
          <WebView
            key={webViewKey}
            source={{ uri: webViewUrl }}
            style={{ width: 1, height: 1 }}
            javaScriptEnabled={false}
            domStorageEnabled={false}
            onShouldStartLoadWithRequest={(req) => {
              return handleWebViewRequest(req.url);
            }}
            onNavigationStateChange={(state) => {
              // Backup: catches redirects that bypass onShouldStartLoadWithRequest
              if (state.url && !state.loading) {
                handleWebViewRequest(state.url);
              }
            }}
            onError={tryNextUrl}
            onHttpError={tryNextUrl}
          />
        </View>
      ) : null}

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={[
          styles.container,
          { paddingTop: topPad + 16, paddingBottom: botPad + 32 },
        ]}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        {/* ── LOGO (tap 5x to open admin) ── */}
        <Animated.View entering={FadeIn.duration(600)} style={styles.logoSection}>
          <TouchableOpacity onPress={handleLogoTap} activeOpacity={1}>
            <Animated.View style={logoStyle}>
              <LinearGradient
                colors={['#00b4ff22', '#00b4ff08', 'transparent']}
                style={styles.logoGlow}
              />
              <View style={styles.logoRow}>
                <MaterialCommunityIcons name="wifi" size={32} color="#00b4ff" />
                <Text style={styles.logoText}>STAR</Text>
                <MaterialCommunityIcons name="wifi" size={32} color="#00b4ff" />
              </View>
            </Animated.View>
          </TouchableOpacity>
          <Text style={styles.logoSub}>Ruijie Network Portal Tool</Text>
        </Animated.View>

        {/* ── STEP 1: KEY ── */}
        <Animated.View entering={FadeInDown.delay(100).duration(500)} style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={styles.stepBadge}>
              <Text style={styles.stepNum}>1</Text>
            </View>
            <Text style={styles.cardTitle}>VIP Key ထည့်ပါ</Text>
            {keyStatus === 'valid' && (
              <Ionicons name="checkmark-circle" size={20} color="#00e676" />
            )}
            {keyStatus === 'invalid' && (
              <Ionicons name="close-circle" size={20} color="#ff4444" />
            )}
          </View>

          <View style={styles.inputRow}>
            <View
              style={[
                styles.inputWrap,
                keyStatus === 'valid' && { borderColor: '#00e67655' },
                keyStatus === 'invalid' && { borderColor: '#ff444455' },
              ]}
            >
              <Ionicons
                name="key-outline"
                size={18}
                color="#4a6b8a"
                style={styles.inputIcon}
              />
              <TextInput
                style={styles.input}
                placeholder="STAR-YYYYMMDD-XXXX"
                placeholderTextColor="#4a6b8a"
                value={keyInput}
                onChangeText={(t) => {
                  setKeyInput(t);
                  if (keyStatus !== 'idle') {
                    setKeyStatus('idle');
                    setKeyResult(null);
                  }
                }}
                autoCapitalize="characters"
                autoCorrect={false}
                editable={keyStatus !== 'valid'}
              />
            </View>
            <TouchableOpacity
              style={[
                styles.actionBtn,
                keyStatus === 'valid' && {
                  backgroundColor: '#00e67622',
                  borderColor: '#00e676',
                },
              ]}
              onPress={keyStatus === 'valid' ? resetKey : checkKey}
              activeOpacity={0.75}
            >
              {keyStatus === 'valid' ? (
                <Ionicons name="refresh" size={18} color="#00e676" />
              ) : (
                <Text style={styles.actionBtnText}>စစ်ဆေး</Text>
              )}
            </TouchableOpacity>
          </View>

          {keyResult ? (
            <View style={styles.statusRow}>
              <GlowDot color={keyStatus === 'valid' ? '#00e676' : '#ff4444'} />
              <Text
                style={[
                  styles.statusText,
                  keyStatus === 'valid'
                    ? { color: '#00e676' }
                    : { color: '#ff4444' },
                ]}
              >
                {keyResult.message}
              </Text>
            </View>
          ) : null}

          <View style={styles.hintRow}>
            <Feather name="info" size={12} color="#4a6b8a" />
            <Text style={styles.hintText}>
              Format: STAR-YYYYMMDD-XXXX | ဆက်သွယ်: @naymin126653
            </Text>
          </View>
        </Animated.View>

        {/* ── STEP 2: NETWORK DETECT ── */}
        <Animated.View entering={FadeInDown.delay(200).duration(500)} style={styles.card}>
          <View style={styles.cardHeader}>
            <View
              style={[
                styles.stepBadge,
                keyStatus !== 'valid' && styles.stepDisabled,
              ]}
            >
              <Text style={styles.stepNum}>2</Text>
            </View>
            <Text
              style={[
                styles.cardTitle,
                keyStatus !== 'valid' && styles.textDisabled,
              ]}
            >
              Network စစ်ဆေးပါ
            </Text>
            {detectStatus === 'found' && (
              <Ionicons name="checkmark-circle" size={20} color="#00e676" />
            )}
          </View>

          <TouchableOpacity
            style={[
              styles.detectBtn,
              keyStatus !== 'valid' && styles.btnDisabled,
              detectStatus === 'detecting' && { opacity: 0.7 },
            ]}
            onPress={startDetect}
            disabled={keyStatus !== 'valid' || detectStatus === 'detecting'}
            activeOpacity={0.75}
          >
            {detectStatus === 'detecting' ? (
              <ActivityIndicator size="small" color="#00b4ff" />
            ) : (
              <MaterialCommunityIcons
                name="wifi-refresh"
                size={18}
                color={keyStatus === 'valid' ? '#00b4ff' : '#4a6b8a'}
              />
            )}
            <Text
              style={[
                styles.detectBtnText,
                keyStatus !== 'valid' && { color: '#4a6b8a' },
              ]}
            >
              {detectStatus === 'detecting'
                ? 'Detecting...'
                : detectStatus === 'found'
                ? 'ထပ်စစ်ဆေး'
                : 'Auto Detect'}
            </Text>
          </TouchableOpacity>

          {/* Detected network info */}
          {detectStatus === 'found' ? (
            <Animated.View
              entering={FadeInDown.duration(400)}
              style={styles.netResult}
            >
              {macAddr ? (
                <NetRow icon="lan" label="MAC" value={macAddr} />
              ) : null}
              {gatewayIp ? (
                <NetRow icon="router-network" label="Gateway" value={gatewayIp} />
              ) : null}
              {deviceIp ? (
                <NetRow icon="ip-network" label="Device IP" value={deviceIp} />
              ) : null}
            </Animated.View>
          ) : null}

          {detectStatus === 'failed' ? (
            <Animated.View entering={FadeInDown.duration(400)} style={styles.statusRow}>
              <GlowDot color="#ff4444" />
              <Text style={[styles.statusText, { color: '#ff4444' }]}>
                Auto Detect မအောင်မြင်ပါ — Manual ထည့်ပါ
              </Text>
            </Animated.View>
          ) : null}

          {/* Manual toggle */}
          {keyStatus === 'valid' ? (
            <TouchableOpacity
              style={styles.manualToggle}
              onPress={() => setShowManual((v) => !v)}
              activeOpacity={0.7}
            >
              <Feather
                name={showManual ? 'chevron-up' : 'chevron-down'}
                size={14}
                color="#4a6b8a"
              />
              <Text style={styles.manualToggleText}>
                {showManual ? 'Manual Input ပိတ်' : 'Manual Input ဖွင့်'}
              </Text>
            </TouchableOpacity>
          ) : null}

          {showManual ? (
            <Animated.View
              entering={FadeInDown.duration(300)}
              style={{ marginTop: 10, gap: 10 }}
            >
              <ManualField
                icon="router-network"
                placeholder="Gateway IP (e.g. 192.168.1.1)"
                value={manualGw}
                onChange={setManualGw}
              />
              <ManualField
                icon="lan"
                placeholder="MAC Address (e.g. aa:bb:cc:dd:ee:ff)"
                value={manualMac}
                onChange={setManualMac}
              />
              <ManualField
                icon="ip-network"
                placeholder="Device IP (e.g. 192.168.1.100)"
                value={manualIp}
                onChange={setManualIp}
              />
            </Animated.View>
          ) : null}
        </Animated.View>

        {/* ── STEP 3: OPEN PORTAL ── */}
        <Animated.View entering={FadeInDown.delay(300).duration(500)} style={styles.card}>
          <View style={styles.cardHeader}>
            <View
              style={[
                styles.stepBadge,
                !canOpenPortal && styles.stepDisabled,
              ]}
            >
              <Text style={styles.stepNum}>3</Text>
            </View>
            <Text
              style={[styles.cardTitle, !canOpenPortal && styles.textDisabled]}
            >
              Portal ဖွင့်ပါ
            </Text>
          </View>

          {canOpenPortal ? (
            <Animated.View
              entering={FadeInDown.duration(400)}
              style={styles.netResult}
            >
              {effectiveMac ? (
                <NetRow icon="lan" label="MAC" value={effectiveMac} />
              ) : null}
              {effectiveGw ? (
                <NetRow icon="router-network" label="Gateway" value={effectiveGw} />
              ) : null}
              {effectiveIp ? (
                <NetRow icon="ip-network" label="Device IP" value={effectiveIp} />
              ) : null}
            </Animated.View>
          ) : null}

          <TouchableOpacity
            style={[styles.portalBtn, !canOpenPortal && styles.btnDisabled]}
            onPress={openPortal}
            disabled={!canOpenPortal}
            activeOpacity={0.8}
          >
            <LinearGradient
              colors={
                canOpenPortal
                  ? ['#00b4ff', '#0080cc']
                  : ['#152040', '#0d1728']
              }
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
              style={styles.portalBtnGrad}
            >
              <MaterialCommunityIcons
                name="web"
                size={22}
                color={canOpenPortal ? '#000' : '#4a6b8a'}
              />
              <Text
                style={[
                  styles.portalBtnText,
                  !canOpenPortal && { color: '#4a6b8a' },
                ]}
              >
                Portal ဖွင့်မည်
              </Text>
            </LinearGradient>
          </TouchableOpacity>

          {!canOpenPortal ? (
            <Text style={styles.hintText}>
              {keyStatus !== 'valid'
                ? 'Step 1: Key စစ်ဆေးပါ'
                : 'Step 2: Network စစ်ဆေးပါ'}
            </Text>
          ) : null}
        </Animated.View>

        {/* ── FOOTER ── */}
        <Animated.View
          entering={FadeInDown.delay(400).duration(500)}
          style={styles.footer}
        >
          <View style={styles.footerRow}>
            <FontAwesome5 name="telegram-plane" size={16} color="#00b4ff" />
            <Text style={styles.footerText}>@naymin126653 | @Leearma6</Text>
          </View>
          <View style={styles.footerRow}>
            <MaterialCommunityIcons name="broadcast" size={14} color="#4a6b8a" />
            <Text style={[styles.footerText, { color: '#4a6b8a', fontSize: 11 }]}>
              t.me/starlinkcodebypass
            </Text>
          </View>
        </Animated.View>
      </ScrollView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  hiddenWebView: {
    position: 'absolute',
    width: 0,
    height: 0,
    overflow: 'hidden',
  },
  container: {
    paddingHorizontal: 20,
    alignItems: 'stretch',
  },
  logoSection: {
    alignItems: 'center',
    marginBottom: 28,
  },
  logoGlow: {
    position: 'absolute',
    width: 200,
    height: 200,
    borderRadius: 100,
    top: -40,
    left: '50%' as any,
    marginLeft: -100,
  },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  logoText: {
    fontSize: 48,
    fontFamily: 'Inter_700Bold',
    color: '#00b4ff',
    letterSpacing: 8,
  },
  logoSub: {
    fontSize: 12,
    fontFamily: 'Inter_400Regular',
    color: '#4a6b8a',
    letterSpacing: 2,
    marginTop: 4,
    textTransform: 'uppercase' as const,
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
  stepBadge: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: '#00b4ff22',
    borderWidth: 1,
    borderColor: '#00b4ff',
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepDisabled: {
    backgroundColor: '#152040',
    borderColor: '#152040',
  },
  stepNum: {
    fontSize: 12,
    fontFamily: 'Inter_700Bold',
    color: '#00b4ff',
  },
  cardTitle: {
    fontSize: 15,
    fontFamily: 'Inter_600SemiBold',
    color: '#e0f0ff',
    flex: 1,
  },
  textDisabled: {
    color: '#4a6b8a',
  },
  inputRow: {
    flexDirection: 'row',
    gap: 10,
    alignItems: 'center',
  },
  inputWrap: {
    flex: 1,
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
  actionBtn: {
    width: 80,
    height: 44,
    borderRadius: 10,
    backgroundColor: '#00b4ff22',
    borderWidth: 1,
    borderColor: '#00b4ff',
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionBtnText: {
    fontSize: 13,
    fontFamily: 'Inter_600SemiBold',
    color: '#00b4ff',
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 10,
  },
  statusText: {
    fontSize: 13,
    fontFamily: 'Inter_500Medium',
    color: '#ffb800',
    flex: 1,
    flexWrap: 'wrap',
  },
  hintRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 10,
  },
  hintText: {
    fontSize: 11,
    fontFamily: 'Inter_400Regular',
    color: '#4a6b8a',
    marginTop: 6,
    flex: 1,
  },
  detectBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    height: 44,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#00b4ff',
    backgroundColor: '#00b4ff11',
  },
  detectBtnText: {
    fontSize: 14,
    fontFamily: 'Inter_600SemiBold',
    color: '#00b4ff',
  },
  btnDisabled: {
    borderColor: '#152040',
    backgroundColor: '#070b14',
  },
  netResult: {
    backgroundColor: '#070b14',
    borderRadius: 10,
    padding: 12,
    marginTop: 10,
    gap: 8,
  },
  netRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  netLabel: {
    fontSize: 12,
    fontFamily: 'Inter_500Medium',
    color: '#4a6b8a',
    width: 70,
  },
  netValue: {
    fontSize: 13,
    fontFamily: 'Inter_600SemiBold',
    color: '#00b4ff',
    flex: 1,
  },
  manualToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 12,
    alignSelf: 'flex-start' as const,
  },
  manualToggleText: {
    fontSize: 12,
    fontFamily: 'Inter_500Medium',
    color: '#4a6b8a',
  },
  portalBtn: {
    borderRadius: 12,
    overflow: 'hidden' as const,
    marginTop: 4,
  },
  portalBtnGrad: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    height: 52,
  },
  portalBtnText: {
    fontSize: 16,
    fontFamily: 'Inter_700Bold',
    color: '#000000',
    letterSpacing: 0.5,
  },
  footer: {
    alignItems: 'center',
    gap: 6,
    marginTop: 10,
  },
  footerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  footerText: {
    fontSize: 12,
    fontFamily: 'Inter_500Medium',
    color: '#00b4ff',
  },
});
