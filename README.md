
# TikTok Follower Discord Bot (Scraping)

Dieser Bot liest die öffentliche TikTok-Profilseite und aktualisiert einen Discord-Channel (Channel-Name für Voice / Topic für Text) mit der aktuellen Follower‑Zahl.

Wichtig
- Dies ist eine Scraping-Lösung (keine offizielle TikTok-API). Scraping kann instabil sein, CAPTCHAs auslösen und ggfs. gegen TikToks Nutzungsbedingungen verstoßen.
- Verwende die Lösung sparsam (Intervall jetzt standardmäßig 4 Stunden).

Setup
1. Python 3.10+ empfohlen.
2. Kopiere `.env.example` zu `.env` und fülle die Werte (DISCORD_TOKEN, GUILD_ID, CHANNEL_ID, TIKTOK_USERNAME).
3. Installiere Dependencies:
   ```
   python -m pip install -r requirements.txt
   ```
4. Starte:
   ```
   python bot.py
   ```

Umgebungsvariablen (`.env`)
- DISCORD_TOKEN: Token deines Discord-Bots.
- GUILD_ID: ID deines Servers (als Zahl).
- CHANNEL_ID: ID des Channels, der aktualisiert werden soll.
- TIKTOK_USERNAME: TikTok-Benutzername (ohne @).
- UPDATE_INTERVAL: Intervall in Sekunden (default 14400 = 4 Stunden).
- USER_AGENT: Optional: User-Agent-String für die HTTP-Requests.

Tipps zur Stabilität
- Erhöhe UPDATE_INTERVAL, wenn du Blockierungen siehst.
- Verwende bei Bedarf eine browser-basierte Lösung (Puppeteer) oder einen Scraping-Service für höhere Robustheit.