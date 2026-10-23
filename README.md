# Sukuna AI Model — Render deployment

## Files
- `main.py`: Telegram bot plus a small Flask homepage and `/health` endpoint.
- `index.html`: standalone homepage template.
- `requirements.txt`: Python dependencies.
- `render.yaml`: Render Web Service configuration.

## Deploy on Render
1. Upload these files to a GitHub repository.
2. In Render, choose **New + → Blueprint** and select the repository, or create a Python Web Service.
3. Build command: `pip install -r requirements.txt`
4. Start command: `python main.py`
5. Add environment variables in Render Dashboard → Environment:
   - `TELEGRAM_TOKEN`: fresh token from @BotFather
   - `OWNER_ID`: your numeric Telegram user ID
   - `NVIDIA_API_KEY`: NVIDIA key for chat fallback
   - `LOVABLE_IMAGE_API_KEY`: key required by your image endpoint, if required by that API
   - `OPENROUTER_API_KEY`: optional OpenRouter chat/Dolphin key
   - `COHERE_API_KEY`: optional Cohere key
   - `LLM7_API_KEY`: optional LLM7 key for the separate chat mode
6. Open the Render service URL; `/` is the homepage and `/health` is the health check.

## Notes
- Keep secrets in hosting environment variables; do not commit `.env` or API keys.
- The bot uses Telegram long polling. Run only one active instance for the same bot token, or Telegram may report polling conflicts.
- Render free services may sleep when idle; for continuous bot availability, check the current Render plan limitations.
- Vercel functions are serverless and are not suitable for running this long-polling bot continuously as-is. Use Render or another persistent Python worker host.
- The Lovable image endpoint's exact auth and request schema must match its provider configuration. This package preserves the current endpoint and common response parsing but does not claim live API validation.
- The SQLite database is local to the service. On hosts with ephemeral filesystems, database contents may be lost on redeploy/restart unless you configure persistent storage or an external database.
