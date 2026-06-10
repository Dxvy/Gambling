# Building the SportPredict Android APK

This guide walks you from a clean checkout to a signed, installable APK.

---

## Prerequisites

| Tool | Version | Download |
|------|---------|----------|
| Node.js | 18 LTS or later | https://nodejs.org |
| JDK | 17 (bundled with Android Studio is fine) | https://adoptium.net |
| Android Studio | Ladybug (2024.2) or later | https://developer.android.com/studio |
| Android SDK | API 35 (target), API 24 (min) | Install via Android Studio SDK Manager |

> **Tip**: Android Studio installs its own JDK. Point `JAVA_HOME` at it if the build
> complains: `C:\Program Files\Android\Android Studio\jbr` on Windows.

---

## One-time setup (first run only)

```bash
# 1 — Install frontend dependencies (already done if you ran npm install)
cd sportpredict/frontend
npm install

# 2 — Initialise the Android platform
#     This creates the android/ folder next to package.json
npx cap add android
```

After `cap add android` you will see a new `android/` directory inside `frontend/`.
Commit it to version control — it contains the Gradle project that Android Studio builds.

---

## Daily development workflow

```bash
cd sportpredict/frontend

# Build the Next.js static export and sync web assets into android/
npm run build:android
```

`build:android` sets `NEXT_STATIC_EXPORT=1` and is equivalent to:
```
NEXT_STATIC_EXPORT=1 next build   →  generates  frontend/out/
npx cap sync android               →  copies out/ into android/app/src/main/assets/public/
```

> The `NEXT_STATIC_EXPORT=1` flag activates `output: "export"` in `next.config.ts`.
> Regular `next build` (used by Vercel and local dev) skips this flag and runs with
> full SSR so that the proxy, route handlers, and Supabase auth all work normally.

To open Android Studio:
```bash
npm run open:android
```

---

## Building a debug APK (quick test)

Inside Android Studio:

1. Wait for Gradle sync to finish (status bar at the bottom).
2. **Build → Build App Bundle(s) / APK(s) → Build APK(s)**
3. Click **locate** in the notification that appears, or find the file at:
   ```
   android/app/build/outputs/apk/debug/app-debug.apk
   ```
4. Install on a connected device or emulator:
   ```bash
   adb install android/app/build/outputs/apk/debug/app-debug.apk
   ```

---

## Building a release APK

### 1 — Generate a keystore (one time)

```bash
keytool -genkey -v \
  -keystore sportpredict-release.keystore \
  -alias sportpredict \
  -keyalg RSA -keysize 2048 \
  -validity 10000
```

Store `sportpredict-release.keystore` somewhere **outside** the repository and back it up.
You cannot re-sign future updates without the same keystore.

### 2 — Configure signing in `android/app/build.gradle`

Open `android/app/build.gradle` and add a `signingConfigs` block, then reference it in
`buildTypes`:

```groovy
android {
    signingConfigs {
        release {
            storeFile     file("../../sportpredict-release.keystore")
            storePassword "YOUR_STORE_PASSWORD"
            keyAlias      "sportpredict"
            keyPassword   "YOUR_KEY_PASSWORD"
        }
    }
    buildTypes {
        release {
            signingConfig     signingConfigs.release
            minifyEnabled     false
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
        }
    }
}
```

> **Security**: never commit passwords to git. Use environment variables or Android Studio's
> [keystore wizard](https://developer.android.com/studio/publish/app-signing) instead.

### 3 — Build

In Android Studio:

1. Select **Build → Generate Signed Bundle / APK…**
2. Choose **APK**.
3. Point to your keystore, enter the alias and passwords.
4. Choose **release** build variant, click **Finish**.
5. Find the APK at:
   ```
   android/app/release/app-release.apk
   ```

Or via Gradle on the command line:

```bash
cd android
./gradlew assembleRelease
# Windows: gradlew.bat assembleRelease
```

Output: `android/app/build/outputs/apk/release/app-release.apk`

---

## Running on a device or emulator

```bash
# List connected devices
adb devices

# Install and launch (debug build)
adb install -r android/app/build/outputs/apk/debug/app-debug.apk

# Live-reload during development (requires Metro / local server)
npx cap run android
```

To use the remote Supabase backend during development, the app contacts
`NEXT_PUBLIC_SUPABASE_URL` at build time — it is baked into the static bundle,
so no extra configuration is needed at runtime.

---

## Updating the app bundle after code changes

```bash
# Re-export and sync (no need to re-open Android Studio)
cd sportpredict/frontend
npm run build:android

# Then in Android Studio: Build → Build APK(s)  (or run via adb)
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `JAVA_HOME is not set` | Point it at the JDK: `export JAVA_HOME=/path/to/jdk` |
| `SDK location not found` | Open Android Studio → SDK Manager, install API 35 |
| White screen in the app | Make sure `webDir: "out"` in `capacitor.config.ts` matches the Next.js output folder |
| `cap sync` says no platforms | Run `npx cap add android` first (one-time step) |
| `next build` fails with image error | Only happens when `NEXT_STATIC_EXPORT=1` is set. `images.unoptimized: true` is activated then — if you added new `<Image>` usages, ensure they use relative paths in `public/` |
| Auth callback doesn't work on device | The `/auth/callback` route requires a server; for mobile, use the Supabase deep-link flow or configure a custom URL scheme in `capacitor.config.ts` (`server.androidScheme`) |

---

## Project file overview

```
sportpredict/frontend/
├── capacitor.config.ts   ← Capacitor config (appId, webDir, plugins)
├── next.config.ts        ← output: "export" activated when NEXT_STATIC_EXPORT=1
├── out/                  ← generated by npm run build:android (gitignored)
└── android/              ← generated by cap add android (commit this)
    └── app/
        └── build/outputs/apk/
            ├── debug/app-debug.apk
            └── release/app-release.apk
```
