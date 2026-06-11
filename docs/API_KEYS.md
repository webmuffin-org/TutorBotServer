# LLM Provider API Keys

Step by step instructions for generating API keys for each LLM
provider supported by TutorBot Server. After creating a key, add it
to your `.env` file using the variable names shown at the end of each
section.

All steps were verified against provider documentation as of
April 2026.

## Table of Contents

- [OpenAI](#openai)
- [Anthropic (Claude)](#anthropic-claude)
- [Google (Gemini)](#google-gemini)
- [Putting it all together](#putting-it-all-together)
- [Changing keys on the deployed server](#changing-keys-on-the-deployed-server)
- [Security checklist](#security-checklist)

---

## OpenAI

Official key management page:
<https://platform.openai.com/api-keys>

1. **Create an account.** Go to <https://platform.openai.com>
   instead of `chatgpt.com`, which is the consumer product. Sign up
   with email or an SSO provider, verify your email, and complete SMS
   phone verification.
2. **Add billing.** OpenAI keys do not work until a payment method is
   on file. In the dashboard, open **Settings > Billing**, add a
   credit card, and purchase an initial credit amount, minimum $5.
   Set a monthly spending limit to cap usage.
3. **Open the API keys page.** In the left sidebar, click
   **API keys**, or go directly to
   <https://platform.openai.com/api-keys>.
4. **Create a new secret key.** Click **Create new secret key**. Give
   it a descriptive name, for example `tutorbot-dev`. Choose **All**
   permissions for a standard integration, or restrict scopes if you
   know exactly what you need.
5. **Copy the key immediately.** It starts with `sk-...`. OpenAI
   shows the full value only once. If you lose it, you must generate a
   new one.
6. **Paste into `.env`:**

   ```bash
   OPENAI_API_KEY=sk-...
   ```

---

## Anthropic (Claude)

Official console: <https://console.anthropic.com>

1. **Create an account.** Go to <https://console.anthropic.com> and
   sign up with email, Google OAuth, or SSO. Verify your email.
2. **Add billing.** Anthropic uses pay as you go. Complete your
   organization profile, then go to **Plans & Billing**, add a credit
   card, and purchase an initial credit balance. A development setup
   usually works well with $10 to $25. Set a monthly spend limit.
3. **Open the API keys page.** In the left sidebar, click
   **API Keys**, or go to
   <https://console.anthropic.com/settings/keys>.
4. **Create a new key.** Click **Create Key**, give it a descriptive
   name, for example `tutorbot-dev`, pick the workspace if prompted,
   and click **Create**.
5. **Copy the key immediately.** It starts with `sk-ant-...`.
   Anthropic shows the full value only once.
6. **Paste into `.env`:**

   ```bash
   ANTHROPIC_API_KEY=sk-ant-...
   ```

---

## Google (Gemini)

Official console: <https://aistudio.google.com>

Use Google AI Studio, not Vertex AI. AI Studio is the developer
platform for the Gemini API and includes a free tier. Vertex AI is
the enterprise path and uses a different authentication model based on
service accounts instead of API keys.

1. **Sign in.** Go to <https://aistudio.google.com> and sign in with
   a Google account. On first visit, accept the Generative AI Terms of
   Service.
2. **Open the API key page.** In the left sidebar, click
   **Get API key**, or go directly to
   <https://aistudio.google.com/apikey>.
3. **Create a key.** Click **Create API key**. You can attach it to
   an existing Google Cloud project or let AI Studio create a new one.
   For a quick setup, choose **Create API key in new project**.
4. **Copy the key immediately.** It starts with `AIza...`. You can
   return to the API key page later to copy the same key again, but
   store it securely now.
5. **Enable billing for higher limits, optional.** The free tier
   allows about 10 requests per minute and 250 per day on Gemini Flash
   models. To raise limits, open the linked Google Cloud project and
   enable billing. No credit card is required for the free tier.
6. **Paste into `.env`:**

   ```bash
   GOOGLE_API_KEY=AIza...
   ```

---

## Putting it all together

In this project, the active provider and the single model for each provider are configured through environment variables.
A minimum working configuration can look like this:

```bash
MODEL_PROVIDER=ANTHROPIC
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-opus-4-7

OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4

GOOGLE_API_KEY=AIza...
GOOGLE_MODEL=gemini-3.1-pro-preview
```

`MODEL_PROVIDER` selects the provider used by every request. The selected provider must have its matching API key configured, for example `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GOOGLE_API_KEY`. Each provider has one configured model through its matching model variable, for example `ANTHROPIC_MODEL`, `OPENAI_MODEL`, or `GOOGLE_MODEL`.

See `.env.example` for the full list of variables.

---

## Changing keys on the deployed server

The instructions above cover local development only. Editing a local
`.env` file has no effect on the hosted production instance of
TutorBot Server. Production keys live inside the server environment,
or a secrets manager, and are read at process start. A running
deployment will not pick up new values until it is restarted.

If you need to rotate or replace any provider key,
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GOOGLE_API_KEY`, on the
live site:

1. **Do not attempt to change production keys yourself.** There is no
   UI for editing production environment variables, and pushing a
   `.env` change through the repository will not update the server.
2. **Contact the engineer who deployed the server.** Ask them to:
   - update the relevant environment variable on the host, or in the
     deployment secret store
   - redeploy or restart the service so the new values are loaded
   - confirm that the new key is active and the old key can be revoked
3. **Revoke the old key only after the new one is confirmed live.**
   This avoids downtime. Revoke it from the provider console once the
   engineer confirms the swap.

If you do not know who deployed the server, check the repository's
deploy history, internal runbook, or ask your team lead before
proceeding.

---

## Security checklist

- Never commit `.env` or any file containing a key. This repo's
  `.gitignore` should already exclude `.env`, but verify it.
- Never paste keys into Slack, email, issue trackers, or public code.
- Never embed keys in frontend or mobile code. API keys are backend
  secrets.
- Rotate keys if you suspect exposure. All three providers let you
  revoke a key and issue a replacement quickly.
- Use separate keys for dev, staging, and production so you can revoke
  one without downtime on the others.
- Set a spend limit on every provider that supports it. OpenAI and
  Anthropic both do.
