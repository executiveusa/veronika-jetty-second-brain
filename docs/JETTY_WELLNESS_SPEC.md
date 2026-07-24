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

---

## **PART 13: THE FLYWHEEL — WHY THREE PIECES BEAT ONE APP**

The mistake that kills most niche software is treating the product as the only thing customers pay for and the only thing that creates value. The system below has three parts that each do something the others can't, and each one makes the other two stronger:

1. **The App (Jetty Wellness)**: Where paying customers run their business.
2. **The Directory**: A free, public, consumer-facing listing of every wellness business in Utah — not just Jetty customers. Top of the funnel, eligible for AI answer engine citation (AEO).
3. **THE JETTY (Blog & Newsletter)**: The editorial layer that makes the Directory findable in Google & AI answer engines while delivering authentic local value.

---

## **PART 14: THE UTAH WELLNESS DIRECTORY — FULL SPEC**

### 14.1 Data Model
- **Businesses**: Name, category, city/service area, hours, contact, description, photos, claimed status, Jetty customer status.
- **Categories**: Yoga Studios, Natural Health Practitioners, Retreat Organizers, Wellness Products/Retail, Massage & Bodywork, Meditation Centers.
- **Locations**: Salt Lake City, Provo/Orem, Park City, St. George, Ogden, Logan, Moab.
- **Reviews**: Sourced reviews (aggregated from Google with attribution, never fabricated).
- **Leads**: Visitor inquiries routed to the business, and newsletter signups captured on page.
- **Claims**: Ownership verification flow when a business claims its free listing.

### 14.2 Programmatic Page Architecture
- `/directory` → all businesses, filterable
- `/directory/[city]` → e.g. `/directory/provo`
- `/directory/[category]` → e.g. `/directory/yoga-studios`
- `/directory/[city]/[category]` → e.g. `/directory/provo/yoga-studios` (42 specific landing pages)
- `/directory/[business-slug]` → individual business profile

---

## **PART 15: THE JETTY — BLOG & NEWSLETTER SYSTEM**

### 15.1 Content Pillars & AI Search (AEO)
- **Cost & Budgeting**: "What it really costs to open a yoga studio in Utah"
- **Risk & Mistakes**: "5 mistakes first-time retreat organizers make in Utah"
- **Comparisons**: "Hot yoga vs. vinyasa: which studio model fits your space"
- **How-To Guides**: "How to plan your first Utah wellness retreat, step by step"
- **Local/Regional**: "Utah's wellness retreat season calendar"
- **Founder Spotlights**: Real interviews with Jetty customers
- **Trust/Selection**: "How to choose a natural healing practitioner in Salt Lake City"

---

## **PART 16: TECHNICAL BUILD — PAYLOAD & SHARED COLLECTIONS**

- **Shared Collections**: `businesses`, `categories`, `locations` shared between Directory & Blog.
- **Internal Linking**: `proposeInternalLinks` links blog articles to category landing pages.
- **Editorial Truth Policy**: Strictly verified claims only. No fake stats or reviews.

---

## **PART 17: REVISED GO-TO-MARKET — DIRECTORY & CONTENT-LED**

- **Weeks 1-4**: Seed Directory with all Utah wellness businesses across 42 landing pages. Publish 10 articles. Launch newsletter.
- **Weeks 5-8**: Directory ranks for long-tail queries & AI answer engines. Business owners claim listings.
- **Weeks 9-12**: Customer founder spotlights published. Retarget Directory claim visitors.
- **Months 4-6**: Organic word-of-mouth referral flywheel compounds.

---

## **PART 18: PAYLOAD SCHEMA — DIRECTORY COLLECTIONS**

### 18.1 Categories
- `name`: text, required, unique (e.g. "Yoga Studios")
- `slug`: text, required, unique, auto-generated
- `description`: textarea
- `icon`: upload (media)
- `seoTitle` / `seoDescription`: text

### 18.2 Locations
- `name`: text, required (e.g. "Provo")
- `slug`: text, required, unique
- `region`: select (Wasatch Front / Utah Valley / Southern Utah / Mountain Resort Towns)
- `description`: richText

### 18.3 Businesses (Core Collection)
- `name`: text, required
- `slug`: text, unique
- `category`: relationship → categories, hasMany
- `location`: relationship → locations, hasMany
- `address`: group (street, city, state, zip)
- `phone` / `email` / `website`: text
- `claimStatus`: select (unclaimed / claimed / verified)
- `jettyCustomer`: checkbox
- `bookingUrl`: text
- `source`: group (`sourceType`, `sourceUrl`, `confidence`, `lastVerifiedDate`) — **Trust Layer**

### 18.4 Access Control Security Rules
- `businesses`: CONTENT_AGENT gets `find: true` but `create/update/delete: false` (Human OWNER/EDITOR only).
- `reviews`: Never agent-generated (`create` restricted to human submission).
- `claims`: OWNER/EDITOR only. CONTENT_AGENT has zero access.

---

## **PART 19: THE JETTY — FIRST 10 ARTICLE BRIEFS**

1. **Brief 1 (Cost)**: "What Does It Really Cost to Open a Yoga Studio in Utah?"
2. **Brief 2 (Cost)**: "How Much Should You Charge for a Wellness Retreat in Utah?"
3. **Brief 3 (Risk)**: "5 Signs Your Yoga Studio Is About to Lose Members"
4. **Brief 4 (Risk)**: "Why Most First-Time Retreat Organizers Lose Money on Their First Event"
5. **Brief 5 (Comparison)**: "Hot Yoga vs. Vinyasa: Which Studio Model Fits Your Utah Space?"
6. **Brief 6 (How-To)**: "How to Plan Your First Wellness Retreat in Utah: A Step-by-Step Guide"
7. **Brief 7 (Common Mistakes)**: "3 Mistakes Natural Health Practitioners Make When Pricing Consultations"
8. **Brief 8 (Local)**: "Utah's Wellness Retreat Season Calendar: When to Book, When to Launch"
9. **Brief 9 (Trust)**: "How to Choose a Natural Healing Practitioner in Salt Lake City"
10. **Brief 10 (Case Study Placeholder)**: "Founder Spotlight: How a Provo Yoga Studio Owner Cut Admin Time by 10 Hours a Week"

---

## **PART 20: THE JETTY DIGEST — FIRST THREE ISSUES**

- **Issue #1**: Welcome to THE JETTY & Studio Startup Costs
- **Issue #2**: The Retreat Issue & Pricing Mistakes
- **Issue #3**: Choosing Who You Trust & Local Practitioner Spotlights

*(See docs/JETTY_NEWSLETTER_ISSUES.md for full templates)*


