#!/bin/bash
# Static analysis of an Android APK: what Android version, CPU, hardware and vendor it needs.
# Nothing from the APK is executed.
APK="$1"
META="$2"
BT=$(ls -d "$ANDROID_HOME"/build-tools/* | sort -V | tail -1)
echo "build-tools: $BT"

echo "== folder listing (name, size, modified, md5)"
python3 - "$META" <<'EOF'
import json,sys
try:
    d=json.load(open(sys.argv[1]))
    for it in d.get('_embedded',{}).get('items',[]):
        print(it.get('name'), it.get('size'), it.get('modified'), it.get('md5'))
except Exception as e:
    print('meta error', e)
EOF

echo "== file"
ls -l "$APK"; sha256sum "$APK"; file "$APK"

echo "== badging"
"$BT/aapt2" dump badging "$APK" 2>&1 | grep -vE "^application-label-|^application-icon-" | head -80

echo "== permissions"
"$BT/aapt2" dump permissions "$APK" 2>&1 | head -80

echo "== manifest: features, activities, intent filters"
"$BT/aapt2" dump xmltree --file AndroidManifest.xml "$APK" 2>&1 \
  | grep -E "E: (uses-sdk|uses-feature|uses-library|activity|activity-alias|service|receiver|action|category|application)|A: http://schemas.android.com/apk/res/android:(name|minSdkVersion|targetSdkVersion|required|screenOrientation|sharedUserId|persistent|directBootAware)" \
  | sed 's/(0x[0-9a-f]*)//g' | head -500

echo "== signing certificate"
"$BT/apksigner" verify --print-certs "$APK" 2>&1 | head -12

echo "== native libraries per CPU"
unzip -l "$APK" | awk '{print $4}' | grep '^lib/' | cut -d/ -f2 | sort | uniq -c
echo "-- library names"
unzip -l "$APK" | awk '{print $4}' | grep '^lib/' | sed 's#^lib/[^/]*/##' | sort -u | head -100

echo "== framework hints"
unzip -l "$APK" | awk '{print $4}' | grep -E "libflutter|libapp\.so|libreactnative|libhermes|index\.android\.bundle|libmonodroid|assets/dexopt|kotlin/" | sort -u | head -20
echo "dex files: $(unzip -l "$APK" | grep -c '\.dex$')"

mkdir -p /tmp/x && cd /tmp/x
unzip -o -q "$APK" 'classes*.dex' 'lib/*/libapp.so' 'assets/index.android.bundle' 2>/dev/null
: > /tmp/str.txt
for f in /tmp/x/classes*.dex /tmp/x/lib/*/libapp.so /tmp/x/assets/index.android.bundle; do
  [ -f "$f" ] && strings -n 4 "$f" >> /tmp/str.txt
done
echo "strings total: $(wc -l < /tmp/str.txt)"

echo "== vendor / device checks (rubetek, model, system props, hardware)"
grep -iE "rubetek|rcp-?0[0-9]|rcp_0|ro\.product|ro\.build\.|ro\.hardware|Build\.MODEL|MANUFACTURER|getprop|/sys/class|/dev/|gpio|relay|poe|ethernet" /tmp/str.txt | cut -c1-140 | sort | uniq -c | sort -rn | head -120

echo "== panel mode / activation / connection"
grep -iE "signalr|panel|activation|activate|stationary|kiosk|launcher|HOME_APP|BOOT_COMPLETED|lockTask|device_owner|DevicePolicy" /tmp/str.txt | cut -c1-140 | sort -u | head -150

echo "== battery / power"
grep -iE "battery|BatteryManager|ACTION_POWER|plugged|charging" /tmp/str.txt | cut -c1-140 | sort -u | head -60

echo "== push services"
grep -iE "firebase|com\.google\.android\.gms|huawei|rustore|hms|pushwoosh|onesignal" /tmp/str.txt | cut -c1-90 | sort -u | head -40

echo "== audio / video / sip"
grep -iE "webrtc|sip|linphone|pjsip|janus|whep|AudioRecord|Camera2|camerax" /tmp/str.txt | cut -c1-110 | sort -u | head -60
echo "== done"
