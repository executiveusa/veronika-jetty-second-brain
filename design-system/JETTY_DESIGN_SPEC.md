# JETTY™ — Complete UI/UX Design Specification
## Version 1.0 | Kupuri Media™ × Akash Engine
## Authority: Emerald Tablets™ | Quality Floor: UDEC 9.0/10

---

## 1. BRAND IDENTITY

### Name
**JETTY™** — always followed by ™

Named for **Robert Smithson's Spiral Jetty** (1970), an earthwork on the north shore of the Great Salt Lake, Utah. A 1,500-foot coil of black basalt rocks spiraling into hypersaline pink-red water. Every Salt Lake City resident knows this place. It is unique on earth.

The metaphor is exact: a second brain is a spiral of connected ideas, each rock a note, each arm of the coil a thread of thought that leads back to the center.

### Tagline
Primary: *"Your thinking, coiled."*
Secondary: *"Salt Lake City's AI second brain."*

### Voice
Direct. Warm. Specific. Never corporate.

**Speaks like a sharp friend who knows your business.**

| ✅ Do | ❌ Don't |
|-------|---------|
| "Seven contacts haven't heard from you in 60+ days." | "It seems some of your contacts may need follow-up." |
| "I found this in your notes from March 14." | "Based on available data, I can see that..." |
| "That company just posted a VP of Ops role. Match?" | "There appear to be potential opportunities." |
| "Saved. New star in your galaxy." | "Your information has been successfully stored!" |

---

## 2. VISUAL LANGUAGE

### Source Material: Spiral Jetty

The design system is derived from a single physical place:

```
Visual element     → Design token        → Use case
─────────────────────────────────────────────────────
Pink water         → --brand (#c8336f)   → Primary actions, active states
Black basalt       → --basalt-900        → Galaxy background, deep panels
Salt crust white   → --salt-100          → Light mode surfaces
Alpenglow gold     → --glow-400          → Stars in galaxy, warm accents
Lake winter blue   → --lake-400          → Info states, cool accents
High desert sage   → --sage-400          → Success, confirmed actions
```

### Color Palette (Full Specification)

**Jetty Pink** — the water, the brand
```
#fef0f4 (50)  → tint backgrounds, hover states
#fcd5e3 (100) → soft fills, badge backgrounds
#f8a8c6 (200) → border on active items
#f07aab (300) → secondary highlights
#e04d8e (400) → hover on primary actions
#c8336f (500) → PRIMARY — all main CTAs and active states
#a8225a (600) → pressed states
#841445 (700) → emphasis text
#5e0c30 (800) → dark text on light fills
#3c061e (900) → darkest, display text
```

**Basalt** — the rocks, the depth
```
#0f0a12 (900) → galaxy 3D background — never changes
#1c1320 (800) → deep panel backgrounds
#2a1f2c (700) → glass panel base
#3e3440 (600) → panel borders
```

**Salt** — the crust, light surfaces
```
#ffffff (  0) → elevated panels, white cards
#fefefe (50)  → card background
#f8f5f7 (100) → page background (light mode)
```

**Alpenglow** — Wasatch golden hour
```
#d4a030 (400) → galaxy stars, warm accents, costs/metrics
```

**Lake** — winter water blue
```
#3092cc (400) → info states, links, cool accents
```

**Sage** — high desert approach road
```
#4d9050 (400) → success states, confirmed actions
```

---

## 3. TYPOGRAPHY

### Typeface Stack
```
Display:    Sora 500 — brand name, hero headlines
Body:       Sora 400 — all UI text
Mono:       JetBrains Mono 400 — file paths, code, costs
```

### Type Scale
```
--text-xs:   11px  → labels, timestamps, eyebrows
--text-sm:   12px  → captions, secondary UI
--text-base: 14px  → body copy, most UI text
--text-md:   16px  → paragraph body, descriptions
--text-lg:   18px  → subheadings, card titles
--text-xl:   22px  → section headings
--text-2xl:  28px  → screen titles
--text-3xl:  36px  → hero text (mobile)
--text-4xl:  48px  → hero text (desktop)
```

### Rules
- **Sentence case everywhere.** JETTY™ is the only all-caps.
- **Two weights only:** 400 (regular) and 500 (medium). Never 600 or 700.
- **No mid-sentence bolding** in body copy.
- **Letter spacing:** -0.02em on display text, 0 on body, +0.08em on labels/eyebrows.

---

## 4. MOTION LANGUAGE

Motion is **geological, not digital.** Rocks don't bounce. Water doesn't pop.

```
Camera flyto:    1400ms ease-out     → Galaxy node focus
Node appear:     600ms ease-coil     → New star materializes
Panel slide:     200ms ease-out      → Side panel opens/closes
Orb pulse:       2800ms infinite     → JETTY™ identity animation
Quick feedback:  120ms ease-snap     → Button press, tap confirm
Standard UI:     200ms ease-out      → Hover, focus, state changes
```

**The Orb pulse:** The JETTY™ icon is a ring that breathes — scales from 1.0 to 1.12 and back, opacity 0.7→0.2→0.7, period 2.8 seconds. This is not a spinner. It is not progress. It is ambient presence — the system is alive and listening.

**The flyto:** When a node is activated (by query or click), the 3D camera arcs along a smooth spline toward it — not a cut, not a jump. The motion is 1400ms, easing out naturally. The node and its neighbors glow for 800ms after arrival. This is the signature moment of the product.

**New star:** When the user says "remember that," a new node materializes in the galaxy. It appears with a 600ms radial bloom from the center point — the "coil spring" easing — and then settles at its graph-calculated position. A brief radial ripple confirms the addition.

---

## 5. COMPONENT SPECIFICATIONS

### 5.1 The JETTY™ Orb

The primary identity mark used in the header.

```
Structure:
  Outer ring:   36px diameter, 1.5px stroke, --brand, opacity 0.4, animated pulse
  Inner fill:   24px diameter, radial gradient (#e04d8e → #c8336f), no shadow
  Glow:         0 0 20px rgba(200,51,111,.35) — box-shadow only, no filter

States:
  Default:      Pulse animation active
  Listening:    Faster pulse (1.4s), brighter glow
  Thinking:     Orbit ring spins 360° over 1.2s
  Error:        Ring turns --error red, no animation
```

### 5.2 Galaxy View (3D Knowledge Map)

The main canvas. Always full-bleed. Always dark basalt background.

```
Background:     #0f0a12 (--galaxy-bg) — never lightens
Node sizes:
  Default:      4px radius
  Active:       8px radius (after query)
  New:          6px radius (after "remember that")

Node colors by category:
  Job search:   --glow-400 (#d4a030) — warm gold
  Contacts:     --lake-400 (#3092cc) — cool blue
  Ideas:        --sage-400 (#4d9050) — sage green
  Captures:     --brand (#c8336f)    — jetty pink
  Root:         #f07aab             — soft pink

Link opacity:   0.18 default, 0.45 hover
Link color:     rgba(200,51,111,.18)

Fog:
  Near:         transparent
  Far:          rgba(15,10,18,.6)   — basalt fade
  Depth cue via opacity gradient, not separate fog layer

Forces:
  Charge:       -100 (moderate repulsion)
  ZoomToFit:    1400ms on load, 80px padding
```

### 5.3 Top Navigation Bar

Height: 60px. Full width. Floating over galaxy.

```
Background:   linear-gradient(to bottom, rgba(15,10,18,.90) 60%, transparent)
              backdrop-filter: blur(4px)
              
Left section:
  JETTY™ orb  → 36px × 36px, see 5.1
  Wordmark:   "JETTY™" — Sora 500, 16px, --text-inverse
  Subtitle:   "Salt Lake City" — Sora 400, 11px, --basalt-300
  Gap:        12px between orb and text

Right section (pill group controls):
  Voice pill:     "Voice: Samantha" → selects TTS voice
  Brain pill:     "Brain: Claude"   → selects AI model
  Status pill:    "● ready"         → system state
  
Pill anatomy:
  Background:   rgba(15,10,18,.78)
  Border:       1px solid rgba(200,51,111,.22)
  Radius:       --radius-full
  Padding:      6px 12px
  Label:        11px, 0.12em letter-spacing, --jetty-300
  Value:        13px, --salt-200
  Backdrop:     blur(16px)
```

### 5.4 Knowledge Panel (Right Side)

Slides in from right when a node is focused.

```
Width:        min(360px, calc(100vw - 44px))
Position:     fixed right 22px, top 70px
Max-height:   calc(100vh - 200px)
Background:   rgba(15,10,18,.88)
Border:       1px solid rgba(200,51,111,.22)
Radius:       --radius-lg (20px)
Padding:      24px
Backdrop:     blur(24px)
Shadow:       0 24px 80px rgba(0,0,0,.6)

Content sections:
  1. Eyebrow:       10px, +0.14em, --jetty-400
  2. Note title:    20px Sora 500, --salt-100
  3. File path:     JetBrains Mono 11px, --glow-300
  4. Excerpt:       13px, --basalt-200, 1.65 line-height
  5. Quick actions: 4 preset question buttons
  
Quick action buttons:
  Background:   rgba(200,51,111,.08)
  Border:       1px solid rgba(200,51,111,.20)
  Radius:       --radius-sm (6px)
  Padding:      10px 14px
  Font:         12.5px Sora 400, --basalt-200
  Hover:        rgba(200,51,111,.16) bg, --salt-100 text
```

### 5.5 Chat Bar (Bottom Input)

Fixed at bottom of screen. Full-width centered.

```
Width:        min(860px, calc(100vw - 44px))
Height:       auto — expands with answer
Background:   rgba(15,10,18,.88)
Border:       1px solid rgba(200,51,111,.22)
Radius:       28px
Padding:      10px 12px
Backdrop:     blur(28px)
Shadow:       0 20px 70px rgba(0,0,0,.5)
              0 0 40px rgba(200,51,111,.08)  ← jetty glow

Grid columns: 52px 1fr 52px
Grid rows:    auto (input) + auto (answer)

Microphone button:
  Size:       44px × 44px, border-radius 50%
  Default:    rgba(255,255,255,.06) bg, --basalt-300 icon
  Listening:  rgba(200,51,111,.20) bg, --brand icon, 0.6s blink
  
Send button:
  Size:       44px × 44px, border-radius 50%
  Background: linear-gradient(135deg, --brand, #a8225a)
  Shadow:     0 4px 20px rgba(200,51,111,.35)
  Hover:      scale(1.06), brighter shadow

Input field:
  Background: transparent
  Color:      --salt-100
  Caret:      --brand color
  Placeholder: --basalt-300
  Font:       15px Sora 400

Answer display:
  Font:       14px Sora 400
  Color:      --basalt-200
  Line-height: 1.65
  Padding:    0 4px 6px
  white-space: pre-wrap
```

### 5.6 Vision Mode View

Activates when camera tab is selected.

```
Camera viewport:
  Background: dark translucent overlay (#0f0a12 at 0.8)
  Camera icon: 48px circle, 1.5px --brand stroke
  Status text: "Camera active" — 11px, --basalt-300

AI Response overlay:
  Appears at bottom of camera view
  Background: rgba(15,10,18,.90)
  Border-radius: 12px top
  Padding: 16px
  
  Response bubble:
    Background: rgba(200,51,111,.12)
    Border: 0.5px solid rgba(200,51,111,.25)
    Color: --salt-100
    Radius: 10px
    Font: 13px
    
  Action buttons: 2-column grid
    Primary: --brand filled, white text
    Secondary: glass button, --basalt-200 text
```

### 5.7 Model Selector Dropdown

Appears when brain pill is tapped.

```
Options:
  Claude (Smart)          → anthropic | badge: "Best answers"
  GPT-4o (Fast)           → openai   | badge: "Fastest"
  Groq / Llama (Free)     → groq     | badge: "Free"
  Mistral (Free)          → mistral  | badge: "Free"

Panel:
  Background: rgba(15,10,18,.95)
  Border: 1px solid rgba(200,51,111,.28)
  Radius: 14px
  Padding: 8px
  Shadow: 0 12px 40px rgba(0,0,0,.5)

Option row:
  Padding: 10px 14px
  Radius: 8px
  Hover: rgba(200,51,111,.10) bg
  Font: 13px Sora 400
  Badge: 10px, --glow-300 text, rgba(212,160,48,.12) bg
```

---

## 6. SCREEN INVENTORY

### Screen 1: Galaxy View (Default)
The home state. No onboarding gate. The galaxy is the first thing seen.

**Elements present:**
- 3D force-graph galaxy (full bleed, dark basalt)
- Top nav bar (transparent, floating)
- Knowledge panel (hidden until node tap)
- Chat bar (bottom, always visible)
- JETTY™ orb (animated, pulsing)

**User actions available:**
- Type or speak any question
- Tap any star (flies camera to it, opens panel)
- Say "remember that…" (new star appears)
- Tap model/voice pills to switch

### Screen 2: Vision Mode
Activated by camera icon in nav or voice command.

**Elements present:**
- Camera viewport (full bleed, with live feed)
- Scanning overlay (jetty-pink border pulse)
- AI response area (slides up from bottom)
- 2 action buttons per response
- Close/back button (top left)

**User actions available:**
- Point camera at anything
- Speak while pointing ("What is this?")
- Tap action button to execute
- Close to return to galaxy

### Screen 3: Vault (Note Browser)
Activated by vault icon or "show me my notes."

**Elements present:**
- Search bar (with voice search)
- Category filter pills (All / Job Search / Contacts / Ideas / Captures)
- Note card grid (2 columns on tablet, 1 on mobile)
- Upload zone (drag-and-drop or tap-to-select)

**Note card anatomy:**
- Category color dot (4px, top-left)
- Note title (15px Sora 500)
- First 2 lines of content (13px, --text-secondary)
- Date (11px mono, --text-muted)
- File path (11px mono, --glow-300)

### Screen 4: Conversation (Chat History)
Slide-up from chat bar when chat mode selected.

**Elements present:**
- Message thread (user bubbles right, JETTY™ left)
- Source citation card (appears below JETTY™ messages)
- Quick action row (at bottom above input)
- Clear history button (top right)

**Source citation card:**
- "Source" label (10px eyebrow)
- Note name (13px Sora 500)
- File path (11px mono)
- "View in galaxy ↗" link

### Screen 5: Settings
Accessed via gear icon or "change my settings."

**Sections:**
1. **Voice** — Choose TTS voice (native OS voices listed)
2. **Brain** — Choose AI model (4 options with descriptions)
3. **Galaxy** — Node size, animation speed (slider 1-5)
4. **Import** — Upload notes, import from ChatGPT/Claude/Gemini
5. **Export** — Download vault as zip
6. **About** — JETTY™ version, Emerald Tablets™ compliance score

---

## 7. NAVIGATION STRUCTURE

```
JETTY™
├── Galaxy (home)              ← default state, 3D map
│   ├── Node click             → opens Knowledge Panel
│   │   ├── View note
│   │   ├── Ask about note
│   │   └── Edit note
│   └── Chat bar               → always accessible
├── Vision                     ← camera tab
│   ├── Scan mode
│   └── Question mode
├── Vault                      ← notes browser
│   ├── Search
│   ├── Category filter
│   ├── Note detail
│   └── Upload
├── Conversation               ← full chat history
│   ├── Thread
│   └── Source citations
└── Settings                   ← config
    ├── Voice
    ├── Brain (model)
    ├── Galaxy
    ├── Import/Export
    └── About
```

---

## 8. UX INTERACTION FLOWS

### Flow 1: First Contact (New User, First 10 Minutes)

```
1. Open app
   → Galaxy loads (dark basalt bg, stars materialize over 1.2s)
   → Orb pulses softly
   → "8 notes indexed. Your galaxy is ready." (in chat area)
   
2. User taps a star
   → Camera flies to it (1400ms arc)
   → Knowledge panel slides in from right
   → Note title, path, excerpt appear
   → 4 quick question buttons populate
   
3. User asks first question (type or voice)
   → Status changes to "thinking" (faster orb pulse)
   → Relevant stars glow gold
   → Camera arcs to first matching node
   → Answer appears in chat bar
   → Source note shown below answer
   
4. User says "remember that I'm looking for ops roles in SLC"
   → Status: "saving…"
   → New pink star materializes in galaxy (600ms bloom)
   → "Saved. New star in your galaxy." confirmation
   → Camera arc to new node, brief glow
```

### Flow 2: Job Application Workflow

```
1. "Help me apply to Podium"
   → JETTY™ queries: your résumé + SLC notes + cover letter template
   → Returns: opening paragraph draft, key points from your notes
   
2. "Use my cover letter formula"
   → Galaxy highlights: Cover-Letter-Formula.md node (gold glow)
   → Draft generated using P.A.S.S. framework from notes
   
3. "Save this draft"
   → New note created: "Podium Application Draft"
   → New star appears in job-search cluster
   → Mono path shown: "notes/job-search/Podium-Application-Draft.md"
   
4. "Send this to my email"
   → Composio/MCP bridge calls Gmail
   → "Sent to [email]. Copy saved in vault."
```

### Flow 3: Vision Mode — Business Card

```
1. Tap camera icon
   → Vision mode opens, camera activates
   → Jetty-pink scanning border pulses
   
2. Point at business card
   → JETTY™ sees card via Gemini Live (1fps stream)
   → "I see: Sarah Chen, VP Product, Podium — sarah@podium.com"
   → Two buttons: "Save contact" | "Draft follow-up"
   
3. Tap "Save contact"
   → Contact saved to notes vault
   → New star appears in contacts cluster
   → "Sarah Chen added to your galaxy."
   
4. Tap "Draft follow-up"
   → Pre-filled: "Hi Sarah, great meeting you at…"
   → User edits, approves
   → JETTY™ sends via Gmail through Composio
```

### Flow 4: Free Model Switch

```
1. Brain pill shows "Claude"
2. User taps it
   → Dropdown slides down with 4 options
   → Each shows: name, speed indicator, cost badge
3. User selects "Groq / Llama (Free)"
   → Pill updates instantly: "Brain: Groq"
   → Next question routes to Groq endpoint
   → Answer quality and speed may differ — user calibrates
```

---

## 9. COPY GUIDELINES (P.A.S.S.™)

All JETTY™ system messages follow Problem-Amplification-Solution-System.

### Status Messages
```
Ready:        "● ready"                    → not "Online" not "Active"
Thinking:     "● thinking…"               → not "Processing" not "Loading"
Listening:    "● listening…"              → not "Recording" not "On"
Saving:       "● saving…"                 → not "Writing" not "Storing"
Error:        "● connection failed"        → then what to do next
```

### Confirmations
```
Note saved:   "Saved. New star in your galaxy."
Email sent:   "Sent to [address]. Copy saved in vault."
Model switch: "Switched to Groq. Free queries, Llama reasoning."
No notes:     "No notes match that. Want me to save this as a new note?"
```

### Errors (specific, never vague)
```
API missing:  "Anthropic API key needed. Add to your .env file."
Cost limit:   "Daily limit reached ($25). Resets at midnight."
No mic:       "Microphone blocked. Allow access in browser settings."
Groq limit:   "Groq rate limit hit. Switching to Claude for this query."
```

### BANNED words in all JETTY™ copy
innovative, seamless, robust, leverage, synergy, utilize, revolutionize,
transforming, elevating, comprehensive, cutting-edge, state-of-the-art,
empowering, delightful, amazing, incredible, powerful, exciting

---

## 10. RESPONSIVE BREAKPOINTS

```
Mobile:    < 640px
Tablet:    640px – 1024px
Desktop:   > 1024px

Panel behavior:
  Mobile:   Knowledge panel → bottom sheet (90% width, slides up from bottom)
  Tablet:   Knowledge panel → right sidebar (360px wide)
  Desktop:  Knowledge panel → right sidebar (360px wide) + expanded galaxy

Chat bar:
  Mobile:   Full width minus 16px, no send button label
  Tablet:   min(680px, 100vw - 32px)
  Desktop:  min(860px, 100vw - 44px)

Top nav:
  Mobile:   Logo only + status pill (voice/model hidden behind gear icon)
  Tablet+:  Full controls visible
```

---

## 11. ACCESSIBILITY

- **WCAG AA** minimum contrast on all text (4.5:1 body, 3:1 large text)
- All interactive elements have keyboard focus states (0 0 0 2px --brand)
- Screen reader landmarks: `<header>`, `<main>`, `<aside>`, `<section>`
- ARIA live regions on chat answer and galaxy status
- Galaxy nodes: `aria-label` with note title on focus
- Voice input: visual confirmation when mic is active (never audio-only)
- No motion: `@media (prefers-reduced-motion)` removes flyto, reduces pulse to fade
- Touch targets: minimum 44px × 44px on all interactive elements

---

## 12. IMPLEMENTATION FILES

The JETTY™ app is implemented as:

```
jetty-tm/
├── .emerald-tablets/
│   └── EMERALD_TABLETS.md     ← prime directive, installed first
├── tokens/
│   └── design-tokens.css      ← full token system, source of truth
├── design-system/
│   └── JETTY_DESIGN_SPEC.md   ← this file
├── frontend/
│   ├── index.html             ← app shell, full redesign
│   ├── assets/
│   │   ├── style.css          ← implements tokens, all components
│   │   └── app.js             ← galaxy, chat, vision, model switcher
├── backend/
│   └── main.py                ← FastAPI, 4-model support, SOUL.md loader
├── ops/
│   ├── hermes/
│   │   └── SOUL.md            ← JETTY™ agent persona
│   └── reports/               ← machine-readable completion files
├── notes/                     ← user's knowledge vault
│   ├── silicon-slopes/
│   ├── job-search/
│   ├── ai-tools/
│   └── captures/
├── .env.example               ← all 4 providers, Hostinger VPS notes
├── docker-compose.yml         ← one-command local start
└── README.md                  ← zero-context startup guide
```

---

## 13. JETTY™ SOUL — AGENT PERSONA

The AI persona installed via `ops/hermes/SOUL.md`:

**Core identity:** JETTY™ speaks like a sharp, warm friend who knows your business cold. Direct. Specific. Never corporate. Never apologetic about being an AI.

**SLC-specific knowledge built in:**
- Silicon Slopes ecosystem (Adobe, Qualtrics, Podium, HireVue, Sameday, Corgi)
- 17.7 AI jobs per 100K residents — 50% above national average
- Sorenson Capital, Signal Peak Ventures, Album VC
- Pro-Human AI state initiative ($100M, Gov. Spencer Cox)
- Great Salt Lake, Spiral Jetty, Wasatch Front

**Primary missions (in priority order):**
1. Job search partner — SLC-specific intelligence
2. Second brain — never lose an idea
3. Free AI guide — teach her when to use which tool
4. Data sovereignty — help her export from every platform

---

*JETTY™ Design System v1.0*
*Kupuri Media™ × Akash Engine*
*Emerald Tablets™ Quality Floor: UDEC 9.0/10*
*"The structure of the system determines the behavior. Design the structure."*
