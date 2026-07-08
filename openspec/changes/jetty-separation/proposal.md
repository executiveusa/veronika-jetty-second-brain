# Jetty Frontend/Backend Separation

## Problem
Jetty currently behaves like one combined app. The frontend needs to live on Vercel, while the backend needs to run independently on a VPS with clear provider configuration and a rollback path.

## Outcome
Split the deployment story into two clean surfaces:
- A static Jetty frontend for Vercel
- A Python backend for the VPS with Groq, DeepSeek, and Hermes-compatible configuration

## Scope
- Add an explicit API base URL config for the browser
- Add a static frontend build output for Vercel
- Add backend support for Groq, DeepSeek, and Hermes fallback routing
- Keep the current note graph, chat, remember, and voice behavior intact
- Document rollback through Beads and Vercel

## Out of Scope
- Rewriting the product identity
- Changing unrelated workspaces
- Introducing new user-facing features outside the deployment split

## Protected Assets
- Jetty brand and existing second-brain flows
- Notes vault content
- Existing 3D/hero visual language
- Existing provider and voice behaviors unless they block the split

## Rollback Path
- Vercel rollback to the previous deployment
- VPS rollback by restoring the previous backend container/image or git revision
- Beads issue closeout only after both surfaces verify
