 # RepRoute Cross-Platform Mobile App — Concept & Design Plan

**Date:** April 2026  
**Status:** Planning — pre-implementation  
**Depends on:** Phases 0–8 MVP completion, Phase 9 pilot validation  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Analysis](#2-current-state-analysis)
3. [Strategic Decision: Why Native Mobile Now](#3-strategic-decision-why-native-mobile-now)
4. [Framework Evaluation & Recommendation](#4-framework-evaluation--recommendation)
5. [Architecture Overview](#5-architecture-overview)
6. [Shared Code Strategy](#6-shared-code-strategy)
7. [Native Capability Unlock Map](#7-native-capability-unlock-map)
8. [Screen-by-Screen Design](#8-screen-by-screen-design)
9. [Navigation Architecture](#9-navigation-architecture)
10. [Offline-First Architecture](#10-offline-first-architecture)
11. [Map & Navigation Integration](#11-map--navigation-integration)
12. [Push Notification Strategy](#12-push-notification-strategy)
13. [Auth & Security](#13-auth--security)
14. [Performance Budget](#14-performance-budget)
15. [Backend API Changes Required](#15-backend-api-changes-required)
16. [Monorepo & Build Pipeline](#16-monorepo--build-pipeline)
17. [Phased Delivery Plan](#17-phased-delivery-plan)
18. [Risk Register](#18-risk-register)
19. [Success Metrics](#19-success-metrics)
20. [Decision Log](#20-decision-log)
21. [Codex Audit Notes (April 19, 2026)](#21-codex-audit-notes-april-19-2026)

---

## 1. Executive Summary

RepRoute is a route-aware field sales prospecting platform for B2B insurance agents. The current product is a React + Vite PWA served through Cloudflare Pages with a FastAPI backend on Render. The PWA strategy was correct for MVP validation — but field agent feedback and the product roadmap (push notifications, turn-by-turn navigation, background sync, camera integration for business cards) demand capabilities that a PWA cannot deliver at parity with native apps.

**Recommendation:** Build a cross-platform native mobile app using **React Native with Expo**. This maximizes code reuse from the existing React + TypeScript frontend (API client, types, offline queue logic, business logic), delivers true native performance for maps and navigation, and unlocks native device capabilities that PWA cannot match. The existing PWA remains the desktop/web fallback; the mobile app becomes the primary field instrument.

**Why not keep PWA-only?** The mvpoutline.md §7 states "Full native iOS/Android apps — PWA is the mobile strategy" is out of scope for MVP. That was the right call. Post-pilot, the limitations are real:
- No reliable background sync on iOS (service workers are killed after ~30s)
- No turn-by-turn navigation integration (Apple Maps / Google Maps deep links require native intents)
- Push notifications on iOS require a native wrapper with APNs entitlements
- Camera access for business card scanning / lead photos requires native media APIs
- Biometric auth (Face ID / fingerprint) for quick re-auth in the field
- Home screen widget for "today's follow-ups" glance

**Why React Native + Expo over alternatives?** The existing team ships React + TypeScript. The entire `frontend/src/api/client.ts` (357 lines of typed API calls), `frontend/src/lib/offlineQueue.ts`, `frontend/src/lib/leadCache.ts`, and `frontend/src/lib/savedLeadCache.ts` can be extracted into a shared package with zero rewrites. No other framework offers this level of code continuity.

---

## 2. Current State Analysis

### 2.1 Existing Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend framework | React 18 + TypeScript 5.9 | Vite 5.4 build |
| Map rendering | MapLibre GL JS 5.9 | PMTiles for vector tiles |
| Auth | Clerk (`@clerk/clerk-react` 5.x) | JWT-based, JWKS verification on backend |
| PWA | `vite-plugin-pwa` 0.21 | Manifest + service worker shell |
| State management | React hooks in `App.tsx` | No external state library |
| Routing (UI) | `react-router-dom` 6.x | Tab-based navigation |
| Backend | FastAPI (Python 3.x) | Render-hosted |
| Database | PostgreSQL (Supabase) | Async via asyncpg + SQLAlchemy |
| Cache / queues | Redis (Upstash) | Rate limiting, enrichment locks, quota counters |
| Routing (roads) | OpenRouteService API | Cached route geometries |
| Geocoding | Photon (Komoot) | With CF Workers KV cache layer |
| Enrichment | Overpass API (OSM) | 50m radius point lookups |
| Validation cron | Cloudflare Worker | Triggers HMAC-secured admin endpoint |
| CI/CD | GitHub Actions | Render auto-deploy on main |

### 2.2 Existing API Surface (consumed by mobile)

The backend API is fully JSON, CORS-enabled, JWT-authenticated, and mobile-ready. No backend rewrite is required for the mobile app. Full API surface:

| Endpoint | Method | Purpose |
|---|---|---|
| `/routes` | POST | Create route (origin, destination, waypoints, corridor) |
| `/routes/{id}` | PATCH | Update corridor width |
| `/routes/{id}/leads` | GET | Retrieve scored, filtered, sorted, grouped leads |
| `/geocode` | GET | Forward + reverse geocode |
| `/saved-leads` | GET/POST | List / create saved leads |
| `/saved-leads/today` | GET | Today dashboard payload |
| `/saved-leads/{id}` | PATCH/DELETE | Update status, follow-up, owner name / delete |
| `/notes` | GET/POST | List / create notes |
| `/leads/{id}/validate` | POST | Trigger validation run |
| `/leads/{id}/validation` | GET | Read validation state |
| `/leads/{id}/validation/{field}` | PATCH | Pin/unpin validation field |
| `/leads/{id}/enrich` | POST | Trigger OSM enrichment |
| `/export/routes/{id}/leads.csv` | GET | Per-route CSV export |
| `/export/saved-leads.csv` | GET | Cross-route CSV export |
| `/health` | GET | Uptime monitoring |

### 2.3 Frontend Components (porting candidates)

| Component | LOC (est.) | Porting strategy |
|---|---|---|
| `api/client.ts` | ~357 | **Extract to shared package** — pure `fetch`, zero React dependency |
| `lib/offlineQueue.ts` | ~120 | **Extract to shared package** — localStorage → AsyncStorage adapter |
| `lib/leadCache.ts` | ~80 | **Extract to shared package** — same pattern |
| `lib/savedLeadCache.ts` | ~60 | **Extract to shared package** — same pattern |
| `lib/toast.ts` | ~50 | Rewrite — native toast/alert system |
| Component JSX | ~2000+ | **Rewrite** — React Native primitives (`View`, `Text`, `ScrollView`, `FlatList`) |
| `app.css` | ~500+ | **Discard** — React Native StyleSheet, no CSS |

### 2.4 Developer Notes from Roadmap

The roadmap explicitly calls out three post-MVP priorities:
1. "Find a way to streamline / optimize / minimize server usage"
2. "plan mobile app / integration"
3. "integrate with google/apple maps?"

This plan addresses all three.

---

## 3. Strategic Decision: Why Native Mobile Now

### 3.1 PWA Limitations Encountered

| Limitation | Impact on field agents | Native solution |
|---|---|---|
| iOS service worker 30-second background limit | Offline queue sync fails if app is backgrounded during drive | Background fetch / BGTaskScheduler (iOS) / WorkManager (Android) |
| No APNs push without native wrapper | Agents miss follow-up reminders while driving | Native push via Expo Push Notifications |
| No turn-by-turn navigation intent | Agents must screenshot the route and switch apps | `apple-maps://` and `google.navigation:` deep links |
| No camera access for lead documentation | Agents can't photograph business cards or storefronts | `expo-camera` + `expo-image-picker` |
| No Face ID / Touch ID | Agents must type password every session | `expo-local-authentication` |
| iOS install friction | "Add to Home Screen" is a 4-tap process most users don't discover | App Store / Play Store install |
| No home screen widgets | Agents can't see today's follow-ups at a glance | iOS WidgetKit / Android Glance via Expo Modules |
| Web map performance on low-end Android | MapLibre GL JS stutters on 2GB RAM devices | `@rnmapbox/maps` (MapLibre variant) — native OpenGL renderer |

### 3.2 Timing Justification

- Phases 0–10 are code-complete or in evidence sign-off
- Phase 9 pilot will validate product-market fit with real agents
- Post-pilot is the correct inflection point: validate with PWA, invest in native once fit is confirmed
- Building native before pilot would have been premature optimization

### 3.3 Coexistence Strategy

The PWA is **not deprecated**. It becomes:
- The desktop/tablet experience (office use)
- The fallback for users who don't want to install an app
- The demo/share experience (send a link, no install required)

The mobile app becomes:
- The primary field instrument
- The App Store / Play Store presence
- The platform for premium native features

Both clients share the same backend API, auth system (Clerk), and data.

---

## 4. Framework Evaluation & Recommendation

### 4.1 Options Evaluated

| Criterion | React Native + Expo | Capacitor (Ionic) | Flutter | Kotlin Multiplatform |
|---|---|---|---|---|
| **Code reuse from existing React codebase** | ⭐⭐⭐⭐⭐ (TypeScript, hooks, API client directly shared) | ⭐⭐⭐⭐⭐ (runs existing web app in WebView) | ⭐ (Dart rewrite of everything) | ⭐ (Kotlin rewrite of everything) |
| **Native map performance** | ⭐⭐⭐⭐⭐ (`@rnmapbox/maps` with MapLibre) | ⭐⭐ (WebView map — same as PWA) | ⭐⭐⭐⭐⭐ (`maplibre-gl-dart`) | ⭐⭐⭐⭐⭐ (native MapLibre SDK) |
| **Native API access** | ⭐⭐⭐⭐ (Expo SDK covers 90% of needs) | ⭐⭐⭐⭐ (plugin system, some gaps) | ⭐⭐⭐⭐⭐ (full native access) | ⭐⭐⭐⭐⭐ (full native access) |
| **Team skill alignment** | ⭐⭐⭐⭐⭐ (React + TypeScript team) | ⭐⭐⭐⭐⭐ (same web stack) | ⭐⭐ (Dart learning curve) | ⭐⭐ (Kotlin learning curve) |
| **Build/deploy simplicity** | ⭐⭐⭐⭐⭐ (EAS Build, OTA updates) | ⭐⭐⭐⭐ (standard mobile CI) | ⭐⭐⭐⭐ (good tooling) | ⭐⭐⭐ (complex gradle/XCFramework setup) |
| **OTA update capability** | ⭐⭐⭐⭐⭐ (Expo Updates — bypass App Review for JS changes) | ❌ (requires full app update) | ❌ (requires full app update) | ❌ (requires full app update) |
| **PWA coexistence** | ⭐⭐⭐⭐⭐ (shared TypeScript packages) | ⭐⭐⭐⭐⭐ (literally the same codebase) | ⭐⭐ (separate codebases) | ⭐⭐ (separate codebases) |
| **Long-term maintenance** | ⭐⭐⭐⭐ (large ecosystem, Meta-backed) | ⭐⭐⭐ (Ionic company backing) | ⭐⭐⭐⭐⭐ (Google-backed, growing) | ⭐⭐⭐ (JetBrains-backed, maturing) |

### 4.2 Recommendation: React Native with Expo (Managed Workflow)

**Rationale:**

1. **Maximum code reuse.** The API client (`client.ts`), all TypeScript types, the offline queue logic, and the lead cache can be extracted into a shared `@reproute/shared` package consumed by both the PWA and the mobile app. This is ~800 lines of business logic that requires zero rewriting.

2. **Team continuity.** The existing developer ships React + TypeScript daily. React Native uses the same mental model (components, hooks, effects) with different primitives (`View` instead of `div`, `StyleSheet` instead of CSS). The learning curve is measured in days, not months.

3. **Expo managed workflow.** Expo handles the entire native build pipeline in the cloud (EAS Build). No local Xcode or Android Studio required for most development. OTA updates via EAS Update let you push JS changes without App Review — critical for a fast-moving field tool.

4. **MapLibre native.** `@rnmapbox/maps` provides a first-class MapLibre renderer on both platforms. This is the same map library already in use (MapLibre GL JS), but rendered natively with OpenGL — dramatically smoother on low-end Android devices.

5. **Clerk React Native support.** Clerk ships `@clerk/clerk-expo` with first-class Expo support, including OAuth, biometric re-auth, and session management. No auth migration needed.

### 4.3 Why Not Capacitor?

Capacitor wraps the existing web app in a native shell. This is the fastest path to "an app in the store" but it inherits every PWA limitation (WebView rendering, no native map performance, poor offline resilience on iOS). It's a stepping stone, not a destination. If we're going to invest in native, invest in native — not a WebView.

### 4.4 Why Not Flutter?

Flutter requires a complete rewrite in Dart. The existing 3,000+ lines of TypeScript (API client, offline queue, cache logic, component logic) cannot be shared. For a solo developer team, the context-switching cost of maintaining two languages and two ecosystems (Dart + TypeScript) is not justified when React Native achieves the same native capability with 5x more code reuse.

---

## 5. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Shared Packages                       │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ @reproute/   │  │ @reproute/   │  │ @reproute/    │  │
│  │ api-client   │  │ offline      │  │ types         │  │
│  │              │  │              │  │               │  │
│  │ fetch-based  │  │ queue + sync │  │ Lead, Route,  │  │
│  │ API calls    │  │ logic        │  │ SavedLead,    │  │
│  │ + JWT auth   │  │              │  │ Note, etc.    │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
│         │                 │                   │          │
└─────────┼─────────────────┼───────────────────┼──────────┘
          │                 │                   │
    ┌─────┴─────┐    ┌─────┴─────┐    ┌────────┴───────┐
    │   PWA     │    │  React    │    │  Backend       │
    │  (Vite)   │    │  Native   │    │  (FastAPI)     │
    │           │    │  (Expo)   │    │                │
    │ Web maps  │    │ Native    │    │ Same API,      │
    │ CSS styles│    │ maps      │    │ same auth,     │
    │ Web SW    │    │ Push notif│    │ same data      │
    │           │    │ Camera    │    │                │
    └───────────┘    │ Biometric │    └────────────────┘
                     │ BG sync   │
                     └───────────┘
```

### 5.1 Package Structure

```
reproute/
├── packages/
│   ├── shared/                    # New: shared TypeScript library
│   │   ├── src/
│   │   │   ├── api/
│   │   │   │   └── client.ts      # Extracted from frontend/src/api/client.ts
│   │   │   ├── types/
│   │   │   │   └── index.ts       # All shared types (Lead, SavedLead, Note, etc.)
│   │   │   ├── offline/
│   │   │   │   ├── queue.ts       # Extracted offline queue core logic
│   │   │   │   ├── storage.ts     # Storage adapter interface
│   │   │   │   └── sync.ts        # Queue flush + retry logic
│   │   │   ├── cache/
│   │   │   │   ├── leadCache.ts
│   │   │   │   └── savedLeadCache.ts
│   │   │   └── index.ts
│   │   ├── package.json
│   │   └── tsconfig.json
│   │
│   ├── mobile/                    # New: React Native + Expo app
│   │   ├── app/                   # Expo Router file-based routing
│   │   │   ├── _layout.tsx        # Root layout (auth gate, bottom tabs)
│   │   │   ├── index.tsx          # Today view (default tab)
│   │   │   ├── route/
│   │   │   │   ├── index.tsx      # Route tab (form + leads)
│   │   │   │   └── [id].tsx       # Lead detail (dynamic route)
│   │   │   ├── saved/
│   │   │   │   ├── index.tsx      # Saved leads tab
│   │   │   │   └── [id].tsx       # Saved lead detail
│   │   │   └── map/
│   │   │       └── index.tsx      # Full-screen map view
│   │   ├── components/
│   │   │   ├── LeadCard.tsx
│   │   │   ├── RouteForm.tsx
│   │   │   ├── FilterChipBar.tsx
│   │   │   ├── ValidationBadge.tsx
│   │   │   ├── ScoreExplanation.tsx
│   │   │   ├── TodaySection.tsx
│   │   │   ├── OfflineBanner.tsx
│   │   │   └── MapView.tsx
│   │   ├── lib/
│   │   │   ├── storage.ts         # AsyncStorage adapter for shared/offline
│   │   │   ├── notifications.ts   # Push notification registration + scheduling
│   │   │   ├── navigation.ts      # Apple Maps / Google Maps deep links
│   │   │   └── biometrics.ts      # Face ID / fingerprint re-auth
│   │   ├── theme/
│   │   │   ├── colors.ts          # Color tokens (from Phase 11 design system)
│   │   │   ├── typography.ts
│   │   │   └── spacing.ts
│   │   ├── app.json               # Expo config
│   │   ├── package.json
│   │   └── tsconfig.json
│   │
│   └── web/                       # Existing: renamed from frontend/
│       ├── src/
│       │   ├── api/               # Imports from @reproute/shared
│       │   ├── components/
│       │   ├── lib/
│       │   ├── pages/
│       │   └── styles/
│       ├── package.json
│       └── vite.config.ts
│
├── backend/                       # Unchanged
├── infra/                         # Unchanged
├── scripts/                       # Unchanged
└── docs/
```

### 5.2 Key Dependencies (Mobile App)

| Package | Purpose |
|---|---|
| `expo` (~53) | Core Expo SDK |
| `expo-router` | File-based routing (same mental model as React Router) |
| `@clerk/clerk-expo` | Auth with biometric re-auth |
| `@rnmapbox/maps` | Native MapLibre GL rendering |
| `expo-location` | GPS + background location |
| `expo-notifications` | Push notifications (APNs + FCM) |
| `expo-camera` | Business card / storefront photo capture |
| `expo-secure-store` | Encrypted token storage |
| `expo-local-authentication` | Face ID / Touch ID / fingerprint |
| `@react-native-async-storage/async-storage` | Key-value storage (offline queue, cache) |
| `expo-linking` | Deep link handling |
| `expo-updates` | OTA JS bundle updates |

---

## 6. Shared Code Strategy

### 6.1 What Gets Shared

The `@reproute/shared` package contains all platform-agnostic TypeScript:

| Module | Source | Porting effort |
|---|---|---|
| API client (all endpoints + types) | `frontend/src/api/client.ts` | Extract as-is; replace `window` checks with portable guard |
| Offline queue core | `frontend/src/lib/offlineQueue.ts` | Extract queue logic; abstract storage behind interface |
| Lead cache | `frontend/src/lib/leadCache.ts` | Extract; abstract storage |
| Saved lead cache | `frontend/src/lib/savedLeadCache.ts` | Extract; abstract storage |
| TypeScript types | Inline in `client.ts` | Already platform-free |

### 6.2 Storage Adapter Interface

The only divergence between PWA and React Native is storage:

```typescript
// packages/shared/src/offline/storage.ts
export interface StorageAdapter {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
  getAllKeys(): Promise<string[]>;
}
```

- **Web:** `localStorage` adapter (existing behavior)
- **React Native:** `AsyncStorage` adapter (from `@react-native-async-storage/async-storage`)

The shared offline queue accepts a `StorageAdapter` at initialization. Zero logic changes.

### 6.3 What Gets Rewritten

| Component | Reason for rewrite |
|---|---|
| All JSX components | React Native uses `<View>`, `<Text>`, `<FlatList>` instead of `<div>`, `<span>`, scrollable `<div>` |
| CSS (`app.css`) | React Native uses `StyleSheet.create()` — no CSS, no selectors, no cascade |
| Map integration | `@rnmapbox/maps` API differs from `maplibre-gl-js` (JS), though concepts are identical |
| Toast system | Native `Alert` or `expo-router` modal instead of DOM-based toast |
| Navigation | `expo-router` (file-based) instead of `react-router-dom` (component-based) |
| Download/export | Native file system (`expo-file-system`) + share sheet (`expo-sharing`) instead of blob download |

---

## 7. Native Capability Unlock Map

### 7.1 Features Unlocked by Native App

| Feature | PWA capability | Native capability | Priority |
|---|---|---|---|
| **Turn-by-turn navigation** | None (switch to Maps app manually) | Deep-link to Apple Maps / Google Maps with destination pre-filled; return to RepRoute after visit | P0 |
| **Push notifications** | Limited (Web Push unsupported on iOS Safari) | Full APNs + FCM with scheduled local notifications for follow-ups | P0 |
| **Background sync** | 30s on iOS, unreliable | Background fetch / BGTaskScheduler — sync offline queue even when app is backgrounded | P0 |
| **Biometric re-auth** | None | Face ID / Touch ID / fingerprint for quick return to app | P1 |
| **Camera** | Partial (getUserMedia) | Full camera for business card capture, storefront photos attached to leads | P1 |
| **Home screen widget** | None | iOS WidgetKit / Android Glance showing today's overdue count | P2 |
| **Offline map tiles** | No (requires network for tiles) | Download vector tile packs for offline map rendering | P2 |
| **Contact integration** | None | Save lead to device contacts with one tap | P2 |
| **Haptic feedback** | Limited (Vibration API) | Full Core Haptics — subtle tap on save, success pattern on sync | P3 |
| **Spotlight / search** | None | Index saved leads in iOS Spotlight / Android App Search | P3 |

### 7.2 Google Maps / Apple Maps Integration

This directly addresses the roadmap developer note: "integrate with google/apple maps?"

**Navigation deep-link strategy:**

```typescript
// packages/mobile/lib/navigation.ts

export async function openNavigation(lat: number, lng: number, name: string): Promise<void> {
  // Apple Maps (iOS default)
  const appleUrl = `maps://app?daddr=${lat},${lng}&dirflg=d&t=m`;
  
  // Google Maps (Android default, also available on iOS)
  const googleUrl = `google.navigation:q=${lat},${lng}`;
  
  // Try platform-appropriate first, fall back to the other
  const platformUrl = Platform.OS === 'ios' ? appleUrl : googleUrl;
  
  const supported = await Linking.canOpenURL(platformUrl);
  if (supported) {
    await Linking.openURL(platformUrl);
  } else {
    // Fallback: open in browser-based Google Maps
    await Linking.openURL(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`);
  }
}
```

**"Navigate" button placement:**
- Lead detail screen: primary action button
- Lead card (swipe action on iOS, long-press menu on Android)
- Map pin callout: navigation arrow icon

**Return-to-app flow:**
- After navigation completes, iOS/Android returns the user to the last foreground app
- On return, RepRoute prompts: "Did you visit {business_name}?" → quick status update to `visited`

---

## 8. Screen-by-Screen Design

### 8.1 Tab Navigation Structure

```
┌─────────────────────────────────────┐
│            Status Bar               │
├─────────────────────────────────────┤
│                                     │
│                                     │
│          Screen Content             │
│                                     │
│                                     │
│                                     │
├─────────────────────────────────────┤
│  🏠 Today  │  🗺 Route  │  📋 Saved │
└─────────────────────────────────────┘
```

Three bottom tabs — matching the existing PWA tab structure exactly. No new navigation concepts for users to learn.

### 8.2 Today View (Default Tab)

```
┌─────────────────────────────────────┐
│ RepRoute         [offline dot] [👤] │
├─────────────────────────────────────┤
│                                     │
│ ── Overdue Follow-ups ────────── 3 ─│
│ ┌─────────────────────────────────┐ │
│ │ 🔴 Smith's Auto Repair         │ │
│ │    Overdue by 2 days            │ │
│ │    [Call] [Navigate] [Update]   │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ 🔴 Johnson Plumbing            │ │
│ │    Overdue by 1 day             │ │
│ │    [Call] [Navigate] [Update]   │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ── Due Today ─────────────────── 2 ─│
│ ┌─────────────────────────────────┐ │
│ │ 🟡 Ace Hardware                │ │
│ │    Due today                    │ │
│ │    [Call] [Navigate] [Update]   │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ── Blue Collar Today ─────────── 4 ─│
│ ┌─────────────────────────────────┐ │
│ │ 🔧 Mike's Welding              │ │
│ │    Score: 82 · Owner: Mike T.   │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ── Ready to Approach ─────────── 3 ─│
│ (Leads with owner name, unsaved)    │
│                                     │
│ ── Recent Route ──────────────── 12 ─│
│ Indianapolis → Carmel · 12 unsaved  │
│ [Resume Route]                      │
│                                     │
├─────────────────────────────────────┤
│  🏠 Today  │  🗺 Route  │  📋 Saved │
└─────────────────────────────────────┘
```

**Key interactions:**
- Swipe right on a card for quick actions (Call / Navigate / Status update)
- Tap card to open detail
- Pull-to-refresh syncs all sections
- Empty state: "Create a route to find prospects" with CTA button
- Each section is collapsible (state persisted in AsyncStorage)

### 8.3 Route Tab

**Phase A: No active route (route creation)**

```
┌─────────────────────────────────────┐
│ Plan Your Route                     │
├─────────────────────────────────────┤
│                                     │
│  📍 From                            │
│  ┌─────────────────────────────────┐│
│  │ Enter origin or use GPS    📍   ││
│  └─────────────────────────────────┘│
│          │                          │
│          │ (route line glyph)       │
│          ▼                          │
│  📍 To                              │
│  ┌─────────────────────────────────┐│
│  │ Enter destination          📍   ││
│  └─────────────────────────────────┘│
│                                     │
│  + Add stops                        │
│                                     │
│  Corridor: [0.5mi] [1mi] [2mi]     │
│                                     │
│  ┌─────────────────────────────────┐│
│  │        Find Prospects           ││
│  └─────────────────────────────────┘│
│                                     │
├─────────────────────────────────────┤
│  🏠 Today  │  🗺 Route  │  📋 Saved │
└─────────────────────────────────────┘
```

**Phase B: Active route (lead discovery)**

```
┌─────────────────────────────────────┐
│ Indianapolis → Carmel · 23 leads    │
│ 12.4 mi · 18 min      [Edit Route]  │
├─────────────────────────────────────┤
│ [Score 40+] [Phone] [Website] ...   │  ← Horizontal filter chips
├─────────────────────────────────────┤
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ 82  Smith's Auto Repair     ✅  │ │  ← Score + name + validation badge
│ │     Auto Service · 0.3 mi      │ │
│ │     📞 (317) 555-0123   🌐     │ │  ← Phone + website indicators
│ │     Owner: John Smith (high)    │ │  ← Owner name + confidence
│ │     [Save]                      │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ 78  Ace Window Cleaning     ⚠️  │ │
│ │     Personal Services · 0.5 mi  │ │
│ │     📞 (317) 555-0456          │ │
│ │     Blue collar                 │ │
│ │     [Save]                      │ │
│ └─────────────────────────────────┘ │
│ ...                                 │
├─────────────────────────────────────┤
│  🏠 Today  │  🗺 Route  │  📋 Saved │
└─────────────────────────────────────┘
```

**Map integration:**
- Floating map toggle button (top-right) opens full-screen map view
- Map shows route line + lead pins
- Tap pin → lead detail bottom sheet
- Map respects active filters

### 8.4 Lead Detail Screen

```
┌─────────────────────────────────────┐
│ ← Back          [Navigate] [⋯ More] │
├─────────────────────────────────────┤
│                                     │
│ Smith's Auto Repair                 │
│ Auto Service · Blue Collar          │
│ 1423 Main St, Indianapolis, IN      │
│                                     │
│ Score: 82  [Why this score? ▾]      │
│ ┌─ Score Explanation ─────────────┐ │
│ │ ✅ Strong fit: Auto Service     │ │
│ │ ✅ Close to route (0.3 mi)      │ │
│ │ ✅ Has phone and website        │ │
│ │ ✅ Website verified             │ │
│ └──────────────────────────────────┘ │
│                                     │
│ ── Contact ─────────────────────────│
│ 📞 (317) 555-0123        [Call]     │
│ 🌐  smithsauto.com        [Open]    │
│ 👤 Owner: John Smith (high conf.)   │
│                                     │
│ ── Validation ──────────────────────│
│ ✅ Validated (92% confidence)        │
│ Website: ✅ Live · Phone: ✅ Valid  │
│ Hours: ⚠️ Needs review              │
│ [Validate Now]                      │
│                                     │
│ ── Status ──────────────────────────│
│ Current: Saved                      │
│ [Called] [Visited] [Follow-up] [✗]  │
│                                     │
│ ── Follow-up ───────────────────────│
│ Due: April 22, 2026                 │
│ [Change Date]                       │
│                                     │
│ ── Notes ───────────────────────────│
│ "Spoke to owner, interested in      │
│  commercial auto." — Apr 18         │
│ [+ Add Note]                        │
│                                     │
├─────────────────────────────────────┤
│  🏠 Today  │  🗺 Route  │  📋 Saved │
└─────────────────────────────────────┘
```

**Key native interactions:**
- Phone number tap → native phone dialer (`tel:` link)
- "Navigate" button → Apple Maps / Google Maps deep link
- "Call" button → native phone dialer
- Swipe on note → delete (with confirmation)
- Share button → native share sheet (export lead info)
- Camera button → attach photo to lead (Phase M3+)

### 8.5 Saved Leads Tab

```
┌─────────────────────────────────────┐
│ Saved Leads               [Export]  │
├─────────────────────────────────────┤
│ [All] [Overdue] [Called] [Visited]  │  ← Status filter chips
├─────────────────────────────────────┤
│                                     │
│ ── Overdue (3) ─────────────────────│
│ ┌─────────────────────────────────┐ │
│ │ 🔴 Smith's Auto Repair         │ │
│ │ Overdue 2 days · Auto Service   │ │
│ │ "Interested in commercial auto" │ │
│ │ [Call] [Navigate] [Update]      │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ── Due Today (2) ───────────────────│
│ ┌─────────────────────────────────┐ │
│ │ 🟡 Ace Hardware                │ │
│ │ Due today · Score 75            │ │
│ │ [Call] [Navigate] [Update]      │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ── Upcoming (8) ────────────────────│
│ ...                                 │
│                                     │
├─────────────────────────────────────┤
│  🏠 Today  │  🗺 Route  │  📋 Saved │
└─────────────────────────────────────┘
```

### 8.6 Full-Screen Map View

```
┌─────────────────────────────────────┐
│ [← Back]              [List View]   │
├─────────────────────────────────────┤
│                                     │
│         ┌─── pin 82                │
│         │                          │
│    pin 78     ───── route line ──── │
│               ─────                │
│        pin 71                       │
│                    pin 65           │
│                                     │
│                                     │
│                                     │
├─────────────────────────────────────┤
│ ┌─ Bottom Sheet (drag handle) ────┐│
│ │ Smith's Auto Repair · Score 82  ││
│ │ 0.3 mi · Auto Service           ││
│ │ [Save] [Navigate] [Details →]   ││
│ └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

---

## 9. Navigation Architecture

### 9.1 Expo Router Structure

```
app/
├── _layout.tsx              # Root: ClerkProvider, Font loading, Notification setup
├── (tabs)/
│   ├── _layout.tsx          # Bottom tab navigator (Today, Route, Saved)
│   ├── index.tsx            # Today view
│   ├── route.tsx            # Route tab (form + leads)
│   └── saved.tsx            # Saved leads tab
├── lead/
│   └── [businessId].tsx     # Lead detail (from route tab)
├── saved-lead/
│   └── [id].tsx             # Saved lead detail (from saved tab)
├── map.tsx                  # Full-screen map (modal)
└── auth/
    └── sign-in.tsx          # Clerk sign-in screen
```

### 9.2 Navigation Flows

| From | To | Trigger | Transition |
|---|---|---|---|
| Any tab | Lead detail | Tap lead card | Slide from right |
| Lead detail | Full-screen map | Tap map preview | Modal (vertical) |
| Route tab | Full-screen map | Tap map toggle | Modal (vertical) |
| Today view | Lead detail | Tap overdue/due card | Slide from right |
| Saved tab | Saved lead detail | Tap card | Slide from right |
| Lead detail | Native navigation | Tap "Navigate" | System intent (leaves app) |
| Any screen | Sign-in | Clerk auth expired | Modal (system) |

### 9.3 Deep Links

| Path | Screen | Example |
|---|---|---|
| `reproute://today` | Today view | Widget tap |
| `reproute://route/{id}` | Route with leads | Resume recent route |
| `reproute://lead/{businessId}` | Lead detail | Push notification tap |
| `reproute://saved/{id}` | Saved lead detail | Push notification tap |

---

## 10. Offline-First Architecture

### 10.1 Offline Strategy (Native)

The existing PWA uses localStorage-backed queues for notes and status changes. The native app uses the same shared queue logic with `AsyncStorage` as the backing store, plus significant enhancements:

| Capability | PWA (current) | Native (target) |
|---|---|---|
| Queue storage | localStorage (5–10MB limit) | AsyncStorage (no practical limit) + SQLite for structured data |
| Queue types | Notes + status changes | Notes + status changes + new saved leads |
| Sync trigger | Foreground only (`online` event + interval) | Foreground + background fetch (iOS BGTaskScheduler / Android WorkManager) |
| Lead data cache | In-memory only (lost on reload) | SQLite local database (persists across sessions) |
| Map tiles | No offline cache | Optional tile pack download for common metro areas |
| Conflict resolution | Last-write-wins by server timestamp | Same strategy (proven sufficient per mvpoutline §5.7) |

### 10.2 Local Data Store

```typescript
// SQLite schema for offline lead storage
interface LeadStore {
  leads: {
    business_id: TEXT PRIMARY KEY,
    route_id: TEXT,
    data: TEXT,           // JSON blob of full Lead object
    saved_at: TEXT,
    synced_at: TEXT,
    dirty: INTEGER        // 1 = local changes not yet synced
  }
  saved_leads: {
    id: TEXT PRIMARY KEY,
    business_id: TEXT,
    status: TEXT,
    next_follow_up_at: TEXT,
    owner_name: TEXT,
    data: TEXT,           // JSON blob of full SavedLead object
    synced_at: TEXT,
    dirty: INTEGER
  }
}
```

This enables:
- Viewing previously loaded leads without network
- Filtering and sorting leads locally (instant, no server round-trip)
- Queueing saves/updates for sync when connectivity returns

### 10.3 Background Sync Flow

```
1. App backgrounded → BGTaskScheduler registers sync task (min interval: 15 min)
2. OS wakes app → flush offline queue to API
3. Success → mark queue items as synced, update local store
4. Failure → retry with exponential backoff, max 3 attempts
5. If queue has items after 3 failures → schedule local notification "Some changes need to sync"
```

---

## 11. Map & Navigation Integration

### 11.1 Native Map Rendering

Replace MapLibre GL JS with `@rnmapbox/maps` configured for MapLibre:

```typescript
// packages/mobile/components/MapView.tsx
import MapboxGL from '@rnmapbox/maps';

MapboxGL.setAccessToken(null); // MapLibre doesn't require a token

// Use the same PMTiles / vector tile source as the PWA
// Configuration: style JSON pointing to existing tile server
```

**Performance gains over WebView map:**
- Native OpenGL rendering (consistent 60fps on low-end devices)
- Hardware-accelerated symbol placement (100+ pins without stutter)
- Native gesture handling (no conflict with scroll gestures)
- Memory-efficient tile management

### 11.2 Navigation Integration Detail

**Scenario: Agent taps "Navigate" on a lead**

```
1. RepRoute opens Apple Maps / Google Maps with destination
2. Agent drives to business, parks
3. Agent switches back to RepRoute
4. App detects significant location change → prompt:
   "You visited Smith's Auto Repair. Update status?"
   [Visited] [Called] [Skip]
5. Agent taps [Visited] → status updated, sync queued
```

**Cross-platform navigation URL strategy:**

| Platform | Primary | Fallback |
|---|---|---|
| iOS | `maps://app?daddr={lat},{lng}` (Apple Maps) | `comgooglemaps://?daddr={lat},{lng}&directionsmode=driving` (Google Maps if installed) |
| Android | `google.navigation:q={lat},{lng}` (Google Maps) | `https://maps.google.com/maps?daddr={lat},{lng}` (browser) |

### 11.3 Route Visualization on Map

The existing `CreateRouteResponse.route_geojson` (LineString) renders directly on the native map using `MapboxGL.ShapeSource` + `MapboxGL.LineLayer`. The corridor buffer is rendered as a semi-transparent polygon fill using the same corridor computation from the backend.

---

## 12. Push Notification Strategy

### 12.1 Notification Types

| Type | Trigger | Action on tap |
|---|---|---|
| Follow-up reminder | `next_follow_up_at` arrives (scheduled local notification) | Open saved lead detail |
| Overdue alert | `next_follow_up_at` passed, status unresolved | Open Today view filtered to overdue |
| Sync failure | Background sync fails after 3 retries | Open app to trigger foreground sync |
| Weekly summary | Monday 8:00 AM local time | Open Today view |
| New leads in area | (Future) New businesses ingested near active routes | Open route tab |

### 12.2 Implementation

**Local notifications (no server required):**
- Schedule follow-up reminders when `next_follow_up_at` is set
- Cancel when follow-up is resolved (status changes to `visited`, `called`, `not_interested`)
- Max 64 scheduled notifications on iOS (LRU eviction — keep most urgent)

**Remote notifications (requires push server — Phase M3+):**
- Backend sends push via Expo Push Service (free tier: 600 notifications/second)
- Requires `expo-push-token` stored on backend (new `user_push_token` table)
- Used for: new leads in territory, team notifications (future)

### 12.3 Notification Permissions Flow

```
1. After first follow-up date is set:
   "RepRoute can remind you about follow-ups. Allow notifications?"
   [Allow] [Not Now]
2. If granted: schedule all pending follow-up reminders
3. If denied: no further prompts; follow-ups visible only in Today view
4. Settings link available in app settings for later enablement
```

---

## 13. Auth & Security

### 13.1 Clerk Integration (React Native)

```typescript
// packages/mobile/app/_layout.tsx
import { ClerkProvider } from '@clerk/clerk-expo';
import { tokenCache } from './lib/clerk-token-cache'; // SecureStore-backed

export default function RootLayout() {
  return (
    <ClerkProvider
      publishableKey={EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY}
      tokenCache={tokenCache}
    >
      <Slot />
    </ClerkProvider>
  );
}
```

**Security measures:**
- JWT tokens stored in `expo-secure-store` (encrypted, device-bound) — not AsyncStorage
- Biometric re-auth after 15 minutes of background (configurable)
- Same Clerk session used across web and mobile (single sign-on)
- Same backend JWT verification — no changes to `backend/app/core/auth.py`

### 13.2 Biometric Re-Authentication

```typescript
// packages/mobile/lib/biometrics.ts
import * as LocalAuthentication from 'expo-local-authentication';

export async function requireBiometricAuth(): Promise<boolean> {
  const hasHardware = await LocalAuthentication.hasHardwareAsync();
  const isEnrolled = await LocalAuthentication.isEnrolledAsync();
  if (!hasHardware || !isEnrolled) return true; // Fallback to session token
  
  const result = await LocalAuthentication.authenticateAsync({
    promptMessage: 'Verify your identity to continue',
    fallbackToPasscode: true,
  });
  return result.success;
}
```

### 13.3 Backend Changes Required: None

The existing backend auth system (`backend/app/core/auth.py`) verifies JWTs from Clerk. The mobile app receives the same JWTs via `@clerk/clerk-expo`. No backend auth changes are required.

---

## 14. Performance Budget

| Metric | Target | Measurement |
|---|---|---|
| Cold start (splash → Today view interactive) | < 2s on iPhone SE | Expo dev tools profiling |
| Route creation → leads displayed | < 4s on 4G (server-inclusive) | Same as PWA target (< 5s) |
| Lead list scroll frame rate | 60fps (native FlatList) | React DevTools Profiler |
| Map render (50 pins + route line) | < 1.5s | Native map profiling |
| Save lead (optimistic) | < 100ms perceived | Local state update before API |
| Offline queue flush (10 items) | < 3s on 4G | Network timing |
| App size (download) | < 25MB (iOS) / < 20MB (Android) | App Store / Play Store |
| Memory usage (steady state) | < 150MB | Xcode Instruments / Android Profiler |

---

## 15. Backend API Changes Required

### 15.1 Required (Phase M1)

| Change | Reason | Effort |
|---|---|---|
| Add `expo_push_token` column to `user` table | Store push notification tokens | Small (migration + user model) |
| `POST /users/push-token` | Register/update push token from mobile | Small (new route) |
| `GET /routes?limit=1` for "recent route" | Today view recent route section (may already be satisfied by `GET /saved-leads/today`) | None (verify existing) |

### 15.2 Recommended (Phase M2)

| Change | Reason | Effort |
|---|---|---|
| `GET /leads?ids=b1,b2,b3` batch endpoint | Sync local store after offline period — fetch only changed leads | Medium (new route + query) |
| `POST /sync/batch` endpoint | Accept batch mutations (notes + status + saves) in single request | Medium (new route + transaction) |
| ETag / `If-Modified-Since` headers on `GET /saved-leads` | Efficient sync — only download changed data | Medium (response headers + query) |

### 15.3 Future (Phase M3+)

| Change | Reason | Effort |
|---|---|---|
| WebSocket / SSE for real-time lead updates | Live collaboration scenarios | Large |
| Photo upload endpoint (`POST /leads/{id}/photos`) | Business card / storefront photos | Medium (S3/R2 integration) |
| Territory GeoJSON endpoint | Define geographic boundaries for push notifications | Large |

### 15.4 Server Usage Optimization

This addresses the roadmap note: "Find a way to streamline / optimize / minimize server usage."

The mobile app reduces server load compared to the PWA:

| Optimization | How | Server impact |
|---|---|---|
| Local SQLite cache | Leads cached locally; only fetch on route change or pull-to-refresh | -50% lead list API calls |
| Batch sync endpoint | Single request for all queued mutations instead of N individual requests | -30% mutation API calls (fewer HTTP connections) |
| ETag-based sync | Only download leads changed since last sync | -70% saved-leads bandwidth for returning users |
| Client-side filtering | Filter and sort locally when data is cached | -40% filtered lead list calls |
| Scheduled background sync | Sync at most once per 15 minutes, not continuous polling | Fewer total requests than foreground-only PWA |

---

## 16. Monorepo & Build Pipeline

### 16.1 Workspace Configuration

```json
// package.json (root)
{
  "name": "reproute",
  "private": true,
  "workspaces": ["packages/*"]
}
```

```json
// packages/shared/package.json
{
  "name": "@reproute/shared",
  "main": "src/index.ts",
  "types": "src/index.ts"
}
```

```json
// packages/mobile/package.json
{
  "name": "@reproute/mobile",
  "dependencies": {
    "@reproute/shared": "workspace:*",
    "expo": "~53.0.0",
    "expo-router": "~4.0.0",
    "@clerk/clerk-expo": "^2.0.0",
    "@rnmapbox/maps": "^10.1.0",
    ...
  }
}
```

### 16.2 Build & Release Pipeline

```
1. Developer pushes to main
2. GitHub Actions runs:
   a. TypeScript typecheck (shared + mobile)
   b. Lint (ESLint)
   c. Unit tests (shared package)
3. On release tag (v*):
   a. EAS Build (iOS + Android in parallel)
   b. EAS Submit (TestFlight + Play Console internal testing)
   c. EAS Update (OTA bundle for existing users not on latest store version)
4. Manual promotion:
   a. TestFlight → App Store review
   b. Play Console internal → production rollout (10% → 50% → 100%)
```

### 16.3 Environment Configuration

| Variable | Purpose | Source |
|---|---|---|
| `EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk auth | Same key as PWA's `VITE_CLERK_PUBLISHABLE_KEY` |
| `EXPO_PUBLIC_API_BASE_URL` | Backend API base | Same value as PWA's `VITE_API_BASE_URL` |
| `EXPO_PUBLIC_MAPLIBRE_STYLE_URL` | Vector tile style JSON | New (may point to same tiles as PWA) |

---

## 17. Phased Delivery Plan

### Phase M1 — Foundation & Core Flow (6–8 weeks)

**Goal:** App in TestFlight and Play Console with the core discovery flow working natively.

**Deliverables:**
- `@reproute/shared` package extracted from existing frontend code
- Expo project scaffolded with Expo Router, Clerk auth, bottom tab navigation
- Today view (reads from `GET /saved-leads/today`)
- Route tab (form + lead list + filter chips, reads from existing API)
- Lead detail screen (score explanation, contact info, validation badge)
- Saved leads tab (list + grouping + status filters)
- Full-screen map (`@rnmapbox/maps` with route line + pins)
- Offline queue for notes and status changes (shared logic from `@reproute/shared`)
- Local SQLite cache for leads
- Biometric re-auth
- Push notification permission flow + local scheduled notifications for follow-ups
- Apple Maps / Google Maps navigation deep links

**Exit criteria:**
- End-to-end flow completable on iOS and Android: route → leads → save → note → navigate → export
- Offline queue syncs correctly after airplane mode test
- Push notifications fire for follow-up reminders
- Navigation deep link opens Maps app and returns to RepRoute

**Blocking dependencies:** Phases 0–8 MVP complete, Phase 9 pilot started

---

### Phase M2 — Offline Resilience & Performance (3–4 weeks)

**Goal:** Mobile app is reliable in real field conditions with spotty connectivity.

**Deliverables:**
- Background sync via BGTaskScheduler / WorkManager
- Batch sync endpoint on backend (`POST /sync/batch`)
- ETag-based efficient sync for saved leads
- Offline map tile pack download for launch metro (optional, PMTiles)
- "Visit detection" prompt when returning from navigation
- Lead photo capture via camera (stored locally, queued for upload)
- Performance profiling and optimization pass
- App Store screenshots, description, privacy policy

**Exit criteria:**
- App works fully offline for 30+ minutes with no data loss
- Background sync completes within 15 minutes of connectivity restoration
- App size < 25MB download
- Cold start < 2s on iPhone SE

**Blocking dependencies:** Phase M1 complete

---

### Phase M3 — App Store Launch & Premium Features (4–6 weeks)

**Goal:** Public launch on App Store and Google Play.

**Deliverables:**
- App Store / Play Store review submission and approval
- Remote push notifications via Expo Push Service (backend integration)
- Home screen widget (iOS WidgetKit + Android Glance)
- Save-to-contacts integration
- Spotlight / App Search indexing for saved leads
- Haptic feedback on key interactions
- Onboarding flow (native version of existing PWA overlay)
- Analytics: screen views, feature usage, crash reporting (Expo Application Services)
- Store listing: screenshots, descriptions, keywords

**Exit criteria:**
- Approved and live on App Store and Google Play
- Pilot agents migrated from PWA to native app
- No regressions vs. PWA feature parity
- Crash-free rate > 99.5%

**Blocking dependencies:** Phase M2 complete, Phase 9 pilot feedback incorporated

---

### Phase M4 — Desktop/Tablet Alignment & Web Deprecation Planning (2–3 weeks)

**Goal:** Ensure web PWA remains optimal for desktop use; plan long-term web scope.

**Deliverables:**
- Web PWA tested and working as desktop-only experience
- Remove mobile-specific web workarounds (iOS install banner, mobile-first CSS)
- Document web PWA as "desktop experience" in marketing/SEO
- Shared package health check: ensure both consumers are using latest types/API
- EAS Update pipeline for rapid mobile hotfixes without App Review

**Exit criteria:**
- Web PWA works correctly on desktop browsers
- No shared package version drift between web and mobile
- EAS Update tested with a real OTA update

---

## 18. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| App Store rejection (review guidelines) | Medium | High | Pre-review checklist: privacy policy, data collection disclosure, no hidden features; TestFlight beta review first |
| MapLibre native SDK performance regression on older Android | Low | Medium | Test on Android 9 / 2GB RAM device in Phase M1; fallback to lighter map style if needed |
| Shared package abstraction leak (web-only APIs in shared code) | Medium | Medium | Strict TypeScript `tsconfig` for shared package targeting `"lib": ["ES2020"]` with no DOM types; CI enforces `tsc --noEmit` in shared package |
| Clerk React Native SDK breaking change | Low | High | Pin Clerk dependency; test EAS Update rollback capability before each Clerk upgrade |
| Expo SDK version conflict with native map library | Medium | Medium | Pin compatible versions; test in Phase M1 before building on top |
| Background sync unreliable on Android OEM battery savers | High | Medium | Document supported devices; offer foreground sync as fallback; don't promise instant sync |
| Developer context-switching between PWA and native | Medium | Low | Shared package minimizes divergence; Phase M4 aligns codebase; most new features target shared code |
| App Store / Play Store annual fees ($99 + $25) | Low | Low | Budget as operational cost; already paying for Clerk, Render, Supabase |

---

## 19. Success Metrics

### 19.1 Adoption Metrics

| Metric | Target (3 months post-launch) |
|---|---|
| Pilot agents using native app (vs. PWA) | ≥ 80% |
| App Store rating | ≥ 4.5 stars |
| Weekly active mobile users | Same as PWA WAU baseline, growing |
| Push notification opt-in rate | ≥ 60% |
| Navigation deep-link usage | ≥ 40% of visited leads navigated via app |

### 19.2 Quality Metrics

| Metric | Target |
|---|---|
| Crash-free rate | > 99.5% |
| Cold start time (p95) | < 2.5s |
| Offline queue sync success rate | > 99% |
| App size | < 25MB |
| OTA update adoption (48 hours) | > 80% |

### 19.3 Business Metrics (inherited from pilot KPIs)

| KPI | Target | Notes |
|---|---|---|
| Route-to-save conversion | ≥ 30% | Same as mvpoutline §16 |
| Save-to-contacted conversion | ≥ 50% | Same as mvpoutline §16 |
| Follow-up completion rate | ≥ 60% | Expected to improve with push notifications |
| Median time: route → first save | < 5 minutes | Expected to improve with native performance |

---

## 20. Decision Log

| # | Decision | Options considered | Rationale |
|---|---|---|---|
| D1 | React Native + Expo (Managed) | Capacitor, Flutter, KMM, pure native | Maximum code reuse from existing React+TS codebase; Expo eliminates native build complexity; OTA updates are a decisive advantage for a field tool |
| D2 | Shared package extraction | Copy-paste, Git submodule, NPM workspace | Yarn/npm workspaces are standard for monorepo TypeScript; zero overhead for type sharing |
| D3 | `@rnmapbox/maps` (MapLibre mode) | Google Maps SDK, Apple Maps SDK, Mapbox GL | Same map library as PWA (MapLibre); same tile source; zero data pipeline changes; no additional API key cost |
| D4 | Clerk Expo SDK | Custom JWT flow, Auth0, Firebase Auth | Same auth provider as PWA; Clerk ships first-class Expo support; SSO across web and mobile with zero backend changes |
| D5 | Expo Router (file-based) | React Navigation (component-based), Solito | File-based routing is standard in Expo; matches Next.js mental model; supports deep links and typed routes out of the box |
| D6 | Keep PWA alive | Redirect mobile to app store, deprecate PWA | PWA remains the desktop experience and the zero-install demo path; mobile users get native app as the primary experience |
| D7 | SQLite for local data | AsyncStorage only, WatermelonDB, Realm | Expo SQLite is built into Expo SDK; no extra dependency; SQL is well-understood; AsyncStorage is insufficient for relational queries |
| D8 | Last-write-wins conflict resolution | CRDT, operational transform, merge prompts | Same strategy as PWA (proven sufficient per mvpoutline §5.7); mobile adds background sync but the edge case of concurrent edits on two devices remains rare for single-rep usage |
| D9 | EAS Build (cloud) | Local Xcode + Android Studio | No local native build tooling required; consistent CI/CD; free tier covers 30 builds/month for iOS and Android |
| D10 | Phased delivery (M1→M4) | Big bang launch | Incremental delivery allows pilot feedback to course-correct; M1 delivers the core value prop; M2/M3 add reliability and store presence |

---

## 21. Codex Audit Notes (April 19, 2026)

This section captures an implementation realism audit against the current roadmap and codebase as of **April 19, 2026**.

### 21.1 Overall Verdict

- The strategy (React Native + Expo, shared logic, PWA desktop fallback) is sound.
- The current plan is **over-scoped in Phase M1** and **optimistic on total duration** unless scope is reduced.
- The plan timing is slightly ahead of roadmap readiness; prerequisite phases are not yet fully closed.

### 21.2 What Is Realistic

- Reusing typed API contracts and core business logic is practical.
- Native deep links for Apple/Google Maps are appropriate and high value for field workflows.
- Keeping web as desktop fallback avoids a disruptive migration and preserves demo/shareability.

### 21.3 Scope and Timing Gaps

- **Prerequisite mismatch:** this document assumes Phases 0–8 complete and Phase 9 underway; the roadmap currently shows Phases 2/3/4/6/7 in progress, Phase 8 not started, and Phase 9 not started.
- **M1 scope is too dense for 6–8 weeks** for a small team: it currently combines shared package extraction, full screen parity, native map, SQLite cache, biometrics, push permission flow, and navigation deep links.
- **"Zero rewrite" expectation is overstated:** shared candidates still contain browser-only assumptions (`window`, `localStorage`, install prompt events, `navigator.onLine`) that must be abstracted.

### 21.4 Backend/API Notes

- "Backend auth changes required: none" is true for JWT validation parity, but M1/M2 still require net-new mobile support endpoints (push token registration and batch sync workflows).
- Batch and sync work should be planned as explicit backend milestones, not implicit follow-ons.

### 21.5 Server Usage Notes

- The optimization objective should not wait for mobile rollout. Current web paths still include N+1-style request patterns (validation hydration and saved-lead note hydration) that are immediate backend load multipliers.
- Recommended: prioritize batch read endpoints and reduced request fan-out in the current PWA while mobile work is being staged.

### 21.6 Recommended Rebaseline

- Re-scope **M1** to: auth, route creation, lead list/detail, save/status/note, deep-link navigation, and basic offline queue.
- Move native-heavy additions (advanced map polish, biometrics, push scheduling, background sync, offline tile packs) to **M2**.
- Treat **15–21 weeks** as a best-case target only under reduced M1 scope; otherwise plan for a longer runway.

### 21.7 Plan Update Guidance

- Keep this document as the strategic reference, but rebaseline dates and phase entry criteria after:
  1. Phase 8 QA completion evidence
  2. Phase 9 pilot baseline KPI capture
  3. confirmation of backend capacity for batch/sync endpoints

---

## Appendix A: Project Directory After Implementation

```
reproute/
├── packages/
│   ├── shared/           # ~1,200 lines extracted from frontend
│   ├── mobile/           # ~4,000 lines new (components, screens, native lib)
│   └── web/              # Existing frontend/, refactored to consume shared
├── backend/              # Unchanged
├── infra/                # Unchanged (+ EAS Build config)
├── scripts/              # Unchanged
└── docs/
    ├── mobileplan.md     # This document
    └── ...
```

## Appendix B: Estimated Effort

| Phase | Duration | Key work |
|---|---|---|
| M1 — Foundation | 6–8 weeks | Shared package extraction, all screens, native map, offline queue, push, navigation |
| M2 — Resilience | 3–4 weeks | Background sync, batch API, offline tiles, camera, performance |
| M3 — Launch | 4–6 weeks | Store submission, remote push, widgets, analytics, onboarding |
| M4 — Alignment | 2–3 weeks | Web scope reduction, shared package audit |
| **Total** | **15–21 weeks** | |

## Appendix C: Dependencies on Existing Roadmap

| This plan assumes | Because |
|---|---|
| Phases 0–8 are complete | Mobile app ships the same features as PWA; incomplete features would create parity gaps |
| Phase 9 pilot is underway | Pilot validates product-market fit before native investment |
| Phase 10 (lead intelligence) is code-complete | Mobile app renders `is_blue_collar`, `owner_name`, grouping, etc. from day one |
| Phase 11 (UI overhaul) can proceed in parallel | Phase 11 is PWA-only CSS redesign; mobile app has its own native design system |
| Backend API is stable | Mobile app consumes the same endpoints; breaking changes affect both clients |

---

*This plan will be updated as pilot feedback informs mobile priorities. The first implementation decision (framework confirmation) should be made after Phase 9 baseline KPIs are established.*
