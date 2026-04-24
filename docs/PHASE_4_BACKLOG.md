# Phase 4 — Strategic Backlog (deferred)

Tasks cu ROI scăzut fără investiție de design suplimentară. Documentate aici
pentru a nu se pierde — active când context business justifică.

## Status la `2026-04-24`

### Task 4.1 — iframe injection for Gmail Compose ✅ infra existentă

`manifest.json` conține `"all_frames": true` în `content_scripts`. Chrome rulează
automat `content.js` în orice iframe same-origin la `document_end`, inclusiv în
frame-uri adăugate dinamic (Gmail compose modal, Outlook Web popup). Task-ul din
planul original presupunea polling manual cu `setInterval(checkIframes, 500)`,
pattern moștenit din extensii MV2 — nu mai e necesar cu MV3 + `all_frames`.

**Zero code change needed.** Manual verification: deschide Gmail compose,
tastează `//shortcut` + Tab. Funcționează confirmat în testing recent.

**Risk:** cross-origin iframes (ex: embed-uri terțe în Gmail) sunt sandbox,
content script-ul nu poate intra. Acest risc e intrinsec browser-ului, nu cod.

### Task 4.2 — `chrome.storage.session` pentru access tokens — DEFERRED

**Motiv defer:** AutoText folosește un SINGUR token (180 zile) via Django
`ExpiringToken`. Nu există separare access/refresh. Mutarea token-ului în
`storage.session` fără backend changes:

- Pro: token pierdut la browser close → mai puțin expus pe disk
- Contra: user trebuie să se re-loghe la FIECARE browser restart — UX regres semnificativ

**Pentru ROI real e nevoie de:**

1. **Backend** — split `ExpiringToken` în:
   - `AccessToken` (30 min, emitere la login + refresh)
   - `RefreshToken` (90 zile, stored server-side cu hash, revocable)
2. **API endpoint** — `POST /api/auth/refresh/` existent, dar semantică schimbată:
   - Input: refresh_token (din body / header X-Refresh-Token)
   - Output: new access_token + opțional new refresh_token (rotating)
3. **Extension** —
   - `chrome.storage.session` → access_token
   - `chrome.storage.local` → refresh_token (criptat cu Web Crypto AES-GCM, key derivat din device ID)
   - `background.js` — pe startup: decrypt refresh, call `/refresh`, store new access
   - pe request 401 → call `/refresh` o dată, retry; dacă și refresh fails → clear all, silent

**Effort estimate:** 2-3 zile (Django model + migration + endpoint + extension
refactor + tests). Non-trivial din cauza migrării existing token-urilor active.

**Când merită:** dacă tokens ajung în hands of attacker (disk forensics pe
laptop pierdut, malware, bug care leaks). Pentru echipă mică internă cu
trust model acceptabil, risc acceptat.

**Tracked as:** GitHub issue (creat cu link către acest document).

### Task 4.3 — `userScripts.execute()` API migration — DEFERRED

**Motiv defer:** migration preventive pentru scenariu care nu e încă activ.
Chrome a anunțat că ar putea impune "runtime host permissions" (consent per-site
pentru `<all_urls>`) în versiuni viitoare, dar NU există deadline public. Sursă:
[developer.chrome.com/blog/resuming-the-transition-to-mv3](https://developer.chrome.com/blog/resuming-the-transition-to-mv3).

**Cost actual al migrării:**

- Static `content_scripts` → dynamic `chrome.userScripts.execute()` per-tab
- User TREBUIE să activeze manual toggle în `chrome://extensions` → onboarding friction
- Requires Chrome ≥135 (martie 2025) → breaking pentru user-i pe versiuni mai vechi
- Rewrite de `background.js` (inject on `tabs.onUpdated`) + test matrix

**Effort estimate:** 1 săptămână + documentație onboarding + test la user.

**Trigger point pentru reactivare:**

- Google anunță data de enforcement pe CWS review (urmărire via Chrome blog)
- User-i raportează prompt-uri de permissions care break UX curent
- Extension intră în CWS review cu flag pe `<all_urls>`

Până atunci: `manifest.json` stays ca acum, documentat în `DEPLOYMENT.md` ca
"extensie internă, nu published la CWS".

## De revizuit

Recheck Phase 4 la:
- **2026-Q4** — MV3 policy updates
- Sau când cresc la >20 user-i (schimbă trust model)
- Sau când apare auditul de securitate formal (legal/compliance trigger)
