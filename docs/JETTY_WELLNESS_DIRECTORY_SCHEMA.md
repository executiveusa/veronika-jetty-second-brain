# Utah Wellness Directory — Field-by-Field Collection Schema & Security Specification

This document defines the complete Payload CMS / PostgreSQL schema for the public Utah Wellness Directory collections (`businesses`, `categories`, `locations`, `reviews`, `leads`, `claims`), including access control policies and trust verification rules.

---

## 1. Collection: `categories`
- `id` (UUID / text, required, primary key)
- `slug` (text, required, unique, indexed) e.g., `"yoga-studios"`
- `name` (text, required) e.g., `"Yoga Studios"`
- `description` (textarea) e.g., `"Top-rated yoga, vinyasa, and hot yoga studios across Utah."`
- `icon` (upload -> media)
- `parentCategory` (relationship -> categories, self)
- `seoTitle` / `seoDescription` (text)

**Access Control**: Read public (published only); create/update/delete restricted to `OWNER`. `CONTENT_AGENT` gets `find: true` only.

---

## 2. Collection: `locations`
- `id` (UUID / text, required, primary key)
- `slug` (text, required, unique) e.g., `"provo"`
- `name` (text, required) e.g., `"Provo / Orem"`
- `region` (select: Wasatch Front / Utah Valley / Southern Utah / Mountain Resort Towns)
- `county` (text)
- `coordinates` (point: lat/lng)
- `description` (richText)
- `heroImage` (upload -> media)
- `seoTitle` / `seoDescription` (text)

**Access Control**: Identical to `categories`.

---

## 3. Collection: `businesses` (Core Collection & Trust Layer)
- `id` (UUID / text, required, primary key)
- `slug` (text, required, unique) e.g., `"wasatch-wellness-studio"`
- `name` (text, required) e.g., `"Wasatch Wellness Studio"`
- `category` (relationship -> categories, hasMany)
- `location` (relationship -> locations, hasMany)
- `address` (group: street, city, state, zip)
- `serviceArea` (text)
- `phone` / `email` / `website` (text)
- `hours` (array: {day, open, close})
- `shortDescription` (textarea, 160 char cap)
- `description` (richText)
- `photos` (array -> media)
- `logo` (upload -> media)
- `claimStatus` (select: unclaimed / claimed / verified, default: unclaimed)
- `claimedBy` (relationship -> users)
- `jettyCustomer` (checkbox)
- `jettyTier` (select: none / DIY / guided / white-glove)
- `bookingUrl` (text)
- `featuredPlacement` (checkbox)
- `socialLinks` (group: instagram, facebook, tiktok)
- `certifications` (array: {name, issuingBody, evidenceUrl})
- `foundedYear` (number)
- `source` (group) — **Trust Layer & Editorial Truth Policy**:
  - `sourceType`: select (public-data / self-submitted / claimed)
  - `sourceUrl`: text
  - `confidence`: select (verified / inferred / unknown)
  - `lastVerifiedDate`: date

**Access Control Security Rule**: `CONTENT_AGENT` gets `find: true` only, and `create/update/delete: false`. Business facts carry real-world liability. Only human `OWNER`/`EDITOR` can create or edit business records.

---

## 4. Collection: `reviews`
- `id` (UUID / text, required, primary key)
- `business` (relationship -> businesses, required)
- `source` (select: google / native / other)
- `sourceUrl` (text, required if source ≠ native)
- `rating` (number, 1-5)
- `text` (textarea)
- `reviewerName` (text)
- `date` (date)
- `verified` (checkbox, true only if pulled via attributed API or confirmed submission)

**Access Control Security Rule**: `create` is NEVER available to `CONTENT_AGENT`. Reviews must never be agent-generated.

---

## 5. Collection: `leads`
- `id` (UUID / text, required, primary key)
- `business` (relationship -> businesses, optional)
- `name` / `email` / `phone` / `message` (text)
- `source` (select: directory-inquiry / newsletter-signup / claim-request)
- `consentGiven` (checkbox, required)
- `createdAt` (date, auto)

**Access Control Security Rule**: `create` public (form submission); `read` restricted to `OWNER` + the claimed business owner.

---

## 6. Collection: `claims`
- `id` (UUID / text, required, primary key)
- `business` (relationship -> businesses, required)
- `claimantName` / `claimantEmail` / `claimantRole` (text)
- `verificationMethod` (select: email-domain-match / phone-verification / manual-review)
- `status` (select: pending / approved / rejected)
- `reviewedBy` (relationship -> users)
- `reviewedAt` (date)

**Access Control Security Rule**: `OWNER`/`EDITOR` only for review actions. `CONTENT_AGENT` has ZERO access to this collection.
