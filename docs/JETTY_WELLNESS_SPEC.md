# JETTY WELLNESS™: Strategic Redesign & Launch Plan
## *The Platform for Non-Technical Wellness Founders in Utah*

---

## **EXECUTIVE SUMMARY**

**Product Vision:** Jetty Wellness™ is a one-time-purchase AI operations platform for non-technical founders in Utah's strategic wellness niche—yoga studios, natural healing practitioners, wellness product distributors, and retreat organizers. Unlike generic SaaS subscription models, Jetty Wellness operates on a **one-time setup fee + optional concierge support** model, positioning it as an investment rather than an ongoing expense.

**Target Market:** 
- Yoga studio owners in Utah (700+ studios)
- Natural healing practitioners (acupuncture, herbalism, energy work)
- Wellness product entrepreneurs (adaptogens, supplements, skincare)
- Retreat organizers and wellness coaches
- Non-technical founders aged 28-55

**Key Differentiator:** "Your wellness business, automated. One setup. Own it forever."

---

## **PART 1: NICHE POSITIONING & MARKET STRATEGY**

### **1.1 The Utah Wellness Ecosystem**
Utah has unique advantages for a wellness niche platform:
- **Fastest growing yoga market** in the US (Salt Lake City, Provo, Park City)
- **Natural health movement hub** (herbal medicine traditions, LDS wellness focus)
- **Destination retreat market** (mountain retreats, Moab spiritual tourism)
- **Non-corporate founder mentality** (bootstrap culture, community-first values)
- **Local first networks** (strong word-of-mouth, tight-knit communities)

### **1.2 Why Founders Choose Jetty Wellness**
Instead of juggling 5+ tools (Calendly, Mailchimp, Stripe, Instagram DMs, manual notes):

**Before (Chaos):**
- Manual appointment scheduling
- Scattered client contacts
- Email/DM conversations lost
- No client history or preferences
- Manual invoice tracking
- Social media scattered
- Time wasted on admin = less time with clients

**After (Jetty Wellness):**
- Automated appointment management
- All client data in one place
- Complete conversation history
- Client preferences remembered
- Automated follow-ups & reminders
- Revenue tracking & payment processing
- Single command: "Remember that Sarah prefers evening sessions and asked about chakra balancing"

### **1.3 Outcome-Based Messaging (Not Features)**

❌ **Bad:** "Jetty Wellness features AI agents, integrations, and workflow automation"

✅ **Good:** 
- "Save 10 hours/week on admin so you can help more clients"
- "Never miss a payment or client birthday again"
- "Scale from 5 clients to 50+ without hiring staff"
- "Own your business data—no monthly bill, no surprise cancellations"

---

## **PART 2: USER PERSONAS & JOURNEYS**

### **Persona 1: Sarah – Yoga Studio Owner**
- **Age:** 38, Provo, Utah
- **Pain:** Managing 25 instructors, 400 members, class schedules, payments, member retention
- **Currently uses:** Google Sheets, Acuity Scheduling, Stripe, Instagram, email
- **Wants:** One dashboard showing members, revenue, class fill rates, instructor schedules
- **Success metric:** "I want to know at a glance which classes are full and which instructors need help"

**Jetty Journey:**
1. Signs up, completes 2-minute "Tell me about your business" conversation
2. Jetty creates initial data model (instructors, classes, members, pricing)
3. Links Stripe, Instagram, email, Google Calendar
4. Jetty automatically:
   - Syncs class schedules
   - Tracks member attendance
   - Sends automated reminders 24h before class
   - Logs revenue by class/instructor
5. Sarah asks: "Show me which classes are underbooked" → dashboard loads instantly
6. Sarah says: "Email all members who haven't attended in 30 days with a $20 comeback offer" → done

---

### **Persona 2: Marcus – Natural Healing Practitioner**
- **Age:** 44, Salt Lake City, solo herbalist practice
- **Pain:** Mixing consultations, product orders, client follow-ups, managing wholesale suppliers
- **Currently uses:** Facebook DMs, Venmo, notebook, email
- **Wants:** Client appointment tracking, herbal formula history, automated re-order reminders
- **Success metric:** "My clients remember what blends I recommended last time without me having to flip through notes"

---

### **Persona 3: Elena – Wellness Retreat Organizer**
- **Age:** 42, Park City, runs 8 annual yoga/meditation retreats
- **Pain:** Managing 150+ attendees, deposits, payment plans, last-minute cancellations, communication chaos
- **Currently uses:** Email, Google Forms, spreadsheets, payment apps
- **Wants:** Retreat waitlist management, automated deposit reminders, attendee communication hub
- **Success metric:** "I want automated reminders for payment deadlines so I'm not chasing people 2 weeks before the retreat"

---

## **PART 3: REDESIGNED UI/UX LAYOUT**

### **3.1 Design Philosophy**
- **Non-technical language** throughout (no "agents," "integrations," "schemas")
- **Outcome-focused**
- **Calming aesthetic** (aligned with wellness values)
- **Voice-first option** (key demographic uses voice commands)
- **Color palette:** Warm earth tones, sage greens, soft blues, warm grays
- **Typography:** Clean sans-serif (accessibility), warm serif for headers (trust)

### **3.2 Information Architecture**

```
JETTY WELLNESS DASHBOARD (/app)
├── HOME (Quick snapshot)
├── CLIENTS (CRM, history, preferences)
├── APPOINTMENTS & CLASSES (Calendar, schedule, check-in)
├── PRODUCTS & SERVICES (Offerings, pricing, inventory)
├── MONEY (Revenue, invoices, payment plans)
├── COMMUNICATIONS (Email/SMS campaigns, reminders)
├── AUTOMATIONS (Reminders, follow-ups, waitlist)
├── CONNECTIONS (Stripe, Google Calendar, Gmail, Instagram)
├── SECOND BRAIN (Mode switch to existing 3D Galaxy view)
└── SETTINGS (Business profile, team, billing)
```

---

## **PART 4: DATABASE SCHEMA & API SPECIFICATION**

```sql
CREATE TABLE businesses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  business_type TEXT NOT NULL, -- studio | solo_practice | retreat | product
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE clients (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  preferences JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  last_contact TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE appointments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  start_time TIMESTAMP WITH TIME ZONE NOT NULL,
  end_time TIMESTAMP WITH TIME ZONE NOT NULL,
  status TEXT DEFAULT 'scheduled', -- scheduled | completed | cancelled | no_show
  notes TEXT
);

CREATE TABLE transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
  client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
  amount DECIMAL(12,2) NOT NULL,
  type TEXT NOT NULL, -- class | product | service | retreat
  date TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE automations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  type TEXT NOT NULL, -- reminder | email_campaign | reengagement | birthday | payment
  trigger JSONB NOT NULL,
  actions JSONB NOT NULL,
  status TEXT DEFAULT 'active', -- active | paused
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  last_run TIMESTAMP WITH TIME ZONE
);
```

---

## **PART 5: BUILD SPECIFICATION & HANDOFF PROMPT**

```html
<jetty-wellness-build-spec>

  <context>
    You are upgrading an existing production app called JETTY™,
    a personal AI second-brain (3D knowledge galaxy + chat + voice)
    built on FastAPI (backend/main.py), vanilla JS/HTML/CSS
    (frontend/), Neo4j graph, and a design-token system
    (tokens/design-tokens.css, design-system/JETTY_DESIGN_SPEC.md).

    We are translating Tasklet's user journeys into a plain-language,
    wellness-business-specific experience called JETTY WELLNESS.
  </context>

  <hard-constraints>
    1. DO NOT delete, rewrite, or restyle the existing 3D second-brain
       interface. It stays fully intact and reachable via a mode switch.
    2. Additive upgrade: Wellness Mode becomes default /app surface.
    3. Plain-language UI (no "agent", "schema", "API", "credits" in UI).
    4. Palette: Sage Green (#9CAF88), Warm Gold (#D4A574), Soft Blue (#6BA3A3), Warm Gray (#8B8680), Cream (#FAF7F2).
  </hard-constraints>

</jetty-wellness-build-spec>
```
