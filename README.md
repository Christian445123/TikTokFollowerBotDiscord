# Social Follower Discord Bot (TikTok + Instagram, Scraping) — konfigurierbar

Dieser Bot liest (per Scraping) die öffentlichen Profilseiten von TikTok und/oder Instagram und aktualisiert Channel(s) im Discord mit den aktuellen Follower-Zahlen.

Wichtig: Scraping ist anfällig für HTML-Änderungen, CAPTCHAs und kann gegen die Nutzungsbedingungen stehen. Nutze sparsam (Default-Intervall = 4 Stunden).

Features
- Wählbar: nur TikTok, nur Instagram oder beide.
- Separate Channel-IDs für TikTok und Instagram möglich, oder ein gemeinsamer Channel.
- Konfiguration über Umgebungsvariablen.

Schnellstart
1. Kopiere `.env.example` zu `.env` und fülle die Werte.
2. Installiere Abhängigkeiten:

   python -m pip install -r requirements.txt

3. Starte:

   python bot.py


Wichtige Umgebungsvariablen
- DISCORD_TOKEN: Token deines Discord-Bots.
- GUILD_ID: ID deines Servers.
- CHANNEL_ID: (optional) allgemeiner Channel, falls keine separaten IDs angegeben sind.
- CHANNEL_ID_TIKTOK: (optional) Channel für TikTok-Updates (überschreibt CHANNEL_ID für TikTok).
- CHANNEL_ID_INSTAGRAM: (optional) Channel für Instagram-Updates (überschreibt CHANNEL_ID für Instagram).
- TIKTOK_USERNAME: TikTok-Benutzername (ohne @).
- INSTAGRAM_USERNAME: Instagram-Benutzername (ohne @).
- ENABLE_TIKTOK: true/false (optional). Wenn nicht gesetzt, wird TikTok aktiviert, falls TIKTOK_USERNAME gesetzt ist.
- ENABLE_INSTAGRAM: true/false (optional). Wenn nicht gesetzt, wird Instagram aktiviert, falls INSTAGRAM_USERNAME gesetzt ist.
- UPDATE_INTERVAL: Intervall in Sekunden (Standard 14400 = 4 Stunden).
- USER_AGENT: Optional: User-Agent-String für HTTP-Requests.

Beispiele
- Nur TikTok in einem Channel:
  - Setze TIKTOK_USERNAME, CHANNEL_ID (oder CHANNEL_ID_TIKTOK) und ENABLE_TIKTOK=true, ENABLE_INSTAGRAM=false.
- Nur Instagram in eigenem Channel:
  - Setze INSTAGRAM_USERNAME, CHANNEL_ID_INSTAGRAM und ENABLE_INSTAGRAM=true, ENABLE_TIKTOK=false.
- Beide in separaten Channels:
  - Setze beide USERNAMEs, CHANNEL_ID_TIKTOK und CHANNEL_ID_INSTAGRAM.
- Beide in einem gemeinsamen Channel:
  - Setze beide USERNAMEs und CHANNEL_ID (oder setze beide Plattform CHANNEL_ID_* auf dieselbe ID).

Tipps zur Stabilität
- Erhöhe UPDATE_INTERVAL, falls Blockierungen/CAPTCHAs auftreten.
- Für hohe Zuverlässigkeit: Browser-basierte Lösung (Puppeteer/Playwright) oder professioneller Scraping-Service.
- Überwache Logs für Parsing-Fehler nach Webseiten-Updates.

Legal & Haftung
- Lies die Terms of Service der Plattformen. Scraping ist auf eigenes Risiko.

Wenn du möchtest, kann ich:
- Separate Update-Intervalle pro Plattform hinzufügen,
- Das Verhalten ändern (statt Channel-Topic eine Nachricht posten),
- Ein Dockerfile / systemd-Service erstellen,
- Die Lösung auf Puppeteer/Node.js portieren (robuster).