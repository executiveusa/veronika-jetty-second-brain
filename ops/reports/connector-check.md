# Connector Check

GitHub connector confirmed write access to `executiveusa/veronika-jetty-second-brain`.

## OpenRouter routing

JETTY™ is now configured for the first live-test path through OpenRouter Auto using the existing OpenAI-compatible `synthia` provider path:

- `MODEL_PROVIDER=synthia`
- `SYNTHIA_GATEWAY_BASE_URL=https://openrouter.ai/api/v1`
- `SYNTHIA_GATEWAY_MODEL=openrouter/auto`
- `SYNTHIA_GATEWAY_API_KEY=<set in Vercel/VPS/Infisical>`

This avoids the previous LLaMA/Groq default path. Groq remains a backup only and has no default model selected in `.env.example`.

## Vercel state

Vercel connector checked project `prj_LoN3O6QkBhhSa0wWEFjsCRnOp8rE` in team `team_5qS6dGopLozD0HWaND62MGtM`, but Vercel returned 404. The visible team project list does not include this project ID.

Current visible team did not yet show a `nuverse-sell` or `veronika-jetty-second-brain` project. Do not claim Vercel deployment complete until the new Vercel project is created/linked or the correct project/team is resolved and live URL is verified.

## Required env for deploy

Production needs at minimum:

- `SYNTHIA_GATEWAY_API_KEY` — OpenRouter key
- `MODEL_PROVIDER=synthia`
- `SYNTHIA_GATEWAY_BASE_URL=https://openrouter.ai/api/v1`
- `SYNTHIA_GATEWAY_MODEL=openrouter/auto`

If Supabase auth is enabled in the next pass:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_JWT_SECRET` backend-only
