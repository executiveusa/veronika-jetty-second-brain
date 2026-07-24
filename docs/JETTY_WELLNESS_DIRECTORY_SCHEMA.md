# Utah Wellness Directory — Field-by-Field Collection Schema Specification

This document defines the complete Payload CMS / PostgreSQL schema for the public Utah Wellness Directory collections (`businesses`, `categories`, `locations`, `reviews`, `leads`, `claims`).

---

## 1. Collection: `categories`
- `id` (UUID / text, required, primary key)
- `slug` (text, unique, indexed) e.g., `"yoga-studios"`
- `name` (text, required) e.g., `"Yoga Studios"`
- `description` (text) e.g., `"Top-rated yoga, vinyasa, and hot yoga studios across Utah."`
- `icon_name` (text) e.g., `"sun-smile"`

## 2. Collection: `locations`
- `id` (UUID / text, required, primary key)
- `slug` (text, unique, indexed) e.g., `"provo"`
- `name` (text, required) e.g., `"Provo / Orem"`
- `region` (text, required) e.g., `"Utah County"`
- `zip_codes` (array of text) e.g., `["84601", "84604", "84606"]`

## 3. Collection: `businesses`
- `id` (UUID / text, required, primary key)
- `slug` (text, unique, indexed) e.g., `"wasatch-wellness-studio"`
- `name` (text, required) e.g., `"Wasatch Wellness Studio"`
- `category_id` (relationship → `categories.id`, required)
- `location_id` (relationship → `locations.id`, required)
- `tagline` (text) e.g., `"Community-first yoga & chakra balancing in Provo"`
- `description` (text / markdown)
- `address` (text) e.g., `"145 N University Ave, Provo, UT 84601"`
- `phone` (text)
- `email` (text)
- `website` (text)
- `hours_json` (jsonb) e.g., `{"mon": "6am-8pm", "tue": "6am-8pm", "sat": "8am-4pm"}`
- `rating_score` (decimal, default: `4.9`)
- `review_count` (integer, default: `24`)
- `is_claimed` (boolean, default: `false`)
- `is_jetty_customer` (boolean, default: `false`)
- `verified_badge` (boolean, default: `false`)
- `booking_url` (text, optional)
- `created_at` (timestamp)

## 4. Collection: `reviews`
- `id` (UUID / text, required, primary key)
- `business_id` (relationship → `businesses.id`, required)
- `author_name` (text, required)
- `rating` (integer, 1-5, required)
- `content` (text, required)
- `source` (text) e.g., `"Google Reviews (Attributed)"`
- `created_at` (timestamp)

## 5. Collection: `leads`
- `id` (UUID / text, required, primary key)
- `business_id` (relationship → `businesses.id`, optional)
- `visitor_name` (text, required)
- `visitor_email` (text, required)
- `message` (text)
- `lead_type` (text) e.g., `"directory_inquiry"`, `"newsletter_signup"`
- `created_at` (timestamp)

## 6. Collection: `claims`
- `id` (UUID / text, required, primary key)
- `business_id` (relationship → `businesses.id`, required)
- `claimant_name` (text, required)
- `claimant_email` (text, required)
- `claimant_phone` (text, required)
- `status` (text, default: `"pending"`) -- `pending` | `verified` | `rejected`
- `verification_notes` (text)
- `created_at` (timestamp)
