# TLEX Android TV App

Android TV wrapper for the [TLEX](../README.md) frontend — loads the existing Next.js web app in a full-screen WebView with TV-optimized layout.

## Architecture

**WebView-based** — no native player, no native library screens. The Android app is a thin shell that:
1. Asks for the TLEX server URL on first launch
2. Opens `{serverUrl}?platform=tv` in a full-screen WebView
3. The frontend detects `platform=tv` and activates TV layout (no sidebar/topbar/bottom nav)

This means ASS subtitles, the existing player, and all frontend features work identically on TV.

## Stack

- **Language**: Kotlin
- **UI**: Jetpack Compose (setup screen) + Android WebView (main app)
- **DI**: Hilt
- **Storage**: DataStore (server URL only)

## Project Structure

```
app/src/main/java/com/tlex/tv/
├── TlexApp.kt                     # @HiltAndroidApp
├── MainActivity.kt                # Single activity + NavHost
├── data/
│   └── local/
│       └── AppPreferences.kt      # DataStore (server_url)
├── di/
│   └── AppModule.kt               # Hilt module
└── ui/
    ├── theme/                     # Color, Type, Theme
    ├── navigation/
    │   ├── Screen.kt              # Setup | WebView
    │   ├── TlexNavGraph.kt        # Setup → WebView routing
    │   └── NavViewModel.kt
    └── screens/
        ├── setup/                 # ServerSetupScreen + ViewModel
        └── webview/               # TvWebView composable
```

## Frontend TV Mode

The Next.js frontend detects TV mode via `?platform=tv` query parameter:

- `src/hooks/use-platform.ts` — `useIsTV()` hook (persisted in `sessionStorage`)
- `src/app/(main)/layout.tsx` — hides Sidebar, TopBar, BottomNav when TV mode is active

TV mode persists across navigation (stored in `sessionStorage`) so the param isn't required on every page.

## Build

Requires Android Studio Hedgehog or newer.

1. Open `android-tv/` as a Gradle project in Android Studio.
2. Wait for Gradle sync to complete.
3. Connect an Android TV device or launch an emulator (TV profile, API 26+).
4. Run the `app` configuration.

On first launch, enter your TLEX server URL (e.g. `http://192.168.1.x:8000` or `http://10.0.2.2:8000` for emulator).

## URL Routing

| Scenario                       | URL to enter              |
|--------------------------------|---------------------------|
| Emulator + backend on same PC  | `http://10.0.2.2:8000`    |
| Physical TV + local PC backend | `http://192.168.1.X:8000` |
| Remote/VPS backend             | Public URL                |
