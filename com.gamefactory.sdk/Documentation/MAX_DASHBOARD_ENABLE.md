# Enable MAX Mediated Networks — One Checklist

`GameFactory > Auto Setup Everything` already imported all 8 MAX mediation adapter
packages, so every channel is **code-ready (✓)**. The only thing left is telling AppLovin
MAX *which networks to mediate* — and that needs your dashboard login (it can't be
scripted; the MAX Management API forbids programmatic network enable).

Do this **once per MAX account**.

> **Easiest path:** open **GameFactory → Readiness** in Unity. It shows live
> code-readiness for every subsystem, has the *Open MAX Dashboard* button, and a tick-box per
> network you check right there as you enable each one in MAX. This markdown is the companion
> that tells you *which credential to paste* for each tick.

---

## 0. One click to open the dashboard
In Unity: **GameFactory → Open MAX Dashboard** (opens `https://dashboard.applovin.com/`).
Or just click the link. (Both buttons also live inside the **GameFactory → Readiness** window.)

Navigate: **Mediation → Manage → Networks** (per app, or account-level if you mediate all apps).

---

## 1. Gather credentials ONCE (before you open the dashboard)
Have these ready in a notepad so you don't bounce between tabs:

| Network | What you'll paste into MAX |
|---|---|
| Meta Audience Network | Meta **App ID** + **App Secret** (Meta Business Manager → Audience Network) |
| Unity Ads | Unity **Game ID** (Unity Operate / Ads dashboard) |
| Vungle (Liftoff) | Vungle **Application ID** + **Reporting API Key** |
| Mintegral | Mintegral **App ID** + **API Key** |
| Pangle (TikTok) | TikTok **App ID** + **App Key** |
| Amazon APS | Amazon **App Key** / **Site ID** |
| InMobi | InMobi **Account ID** (+ placement IDs if prompted) |
| Chartboost | Chartboost **App ID** + **App Signature** |

> You only need the ones you actually want to run. For "connect all mainstream EU/US
> channels", that's all 8 above.

---

## 2. Enable checklist (tick as you go)

- [ ] **Meta Audience Network** — Mediation → Networks → Meta → Enable → paste App ID + Secret → Save
- [ ] **Unity Ads** — Mediation → Networks → Unity Ads → Enable → paste Game ID → Save
- [ ] **Vungle** — Mediation → Networks → Vungle → Enable → paste App ID + API Key → Save
- [ ] **Mintegral** — Mediation → Networks → Mintegral → Enable → paste App ID + API Key → Save
- [ ] **Pangle** — Mediation → Networks → Pangle → Enable → paste App ID + App Key → Save
- [ ] **Amazon APS** — Mediation → Networks → Amazon → Enable → paste App Key / Site ID → Save
- [ ] **InMobi** — Mediation → Networks → InMobi → Enable → paste Account ID → Save
- [ ] **Chartboost** — Mediation → Networks → Chartboost → Enable → paste App ID + Signature → Save

---

## 3. Verify
Back in Unity, run **GameFactory → Setup Project** (or Auto Setup Everything again) — the
readiness report now shows each enabled network as `✓` (adapter imported **and** dashboard
enabled). Anything still `•` means it's enabled in code but not yet switched on in MAX.

---

## Alternative: MAX Integration Manager
AppLovin's **MAX Integration Manager** (Unity window, shipped with the MAX package) can
auto-download/import adapter packages and walk you through network enablement with fewer
clicks. If you prefer a GUI wizard over the dashboard website, use that instead of step 2 —
the end result (networks enabled in MAX) is identical.

> Note: neither path removes the login. AppLovin requires your account credentials to link
> a network's ad inventory to your app — that's by design, not a gap in this SDK.
