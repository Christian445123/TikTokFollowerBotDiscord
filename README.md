Social Follower Discord Bot (TikTok + Instagram — Scraping)

Kurzbeschreibung
Dieser Bot liest (per Scraping) öffentliche Profilseiten von Instagram und TikTok und aktualisiert einen Discord-Channel mit den aktuellen Followerzahlen.

Wichtig
- Dies ist eine Scraping-Lösung — keine offiziellen APIs. Scraping kann instabil sein (HTML/JSON-Änderungen), CAPTCHAs auslösen oder durch Rate‑Limits/Blocking behindert werden.
- Verwende die Lösung sparsam (Standard-Intervall = 4 Stunden). Für produktiven Einsatz ist die offizielle API (Instagram Graph API / TikTok Open Platform) die zuverlässigere Alternative.

Features
- Unterstützt Instagram und TikTok (einzeln oder beide).
- Option: separate Channel-IDs pro Plattform oder ein gemeinsamer Channel.
- Optional: nutze eine funktionierende Profil-URL (z. B. INSTAGRAM_PROFILE_URL), wenn diese bei dir zuverlässig arbeitet.
- Optional: setze ein Instagram‑Cookie (z. B. sessionid) falls Requests geblockt werden.
- Konfiguration über .env.

Quickstart (Schritt für Schritt)
1) Dateien
- Lege die Dateien bot.py, requirements.txt und .env.example in ein Verzeichnis.
- Kopiere .env.example zu .env und passe die Werte an.

2) Python‑Umgebung
- Empfohlen: Python 3.10+
- Abhängigkeiten installieren:
  python -m pip install -r requirements.txt

3) Discord Bot einrichten
- Erstelle in der Discord Developer Console eine Anwendung und einen Bot.
- Gib dem Bot diese Rechte (je nach Methode): Manage Channels (wenn du Channel-Name/Topic ändern willst) oder Send Messages / Manage Messages (wenn du Nachrichten postest).
- Lade den Bot auf deinen Server.
- Aktiviere in Discord "Developer Mode" (Einstellungen → Erweitert) und kopiere:
  - Server ID (GUILD_ID)
  - Channel ID(s) (CHANNEL_ID, CHANNEL_ID_INSTAGRAM, CHANNEL_ID_TIKTOK)
- Setze DISCORD_TOKEN und GUILD_ID in .env.

4) Konfiguration (.env)
Minimal benötigte Variablen:
- DISCORD_TOKEN = dein_bot_token
- GUILD_ID = 123456789012345678
- CHANNEL_ID = 987654321098765432 (Fallback oder gemeinsamer Channel)
- INSTAGRAM_USERNAME = heimatfront24_7official (oder setze INSTAGRAM_PROFILE_URL)

Wichtige optionale Variablen:
- CHANNEL_ID_INSTAGRAM — Channel nur für Instagram
- CHANNEL_ID_TIKTOK — Channel nur für TikTok
- TIKTOK_USERNAME — falls TikTok gewünscht
- UPDATE_INTERVAL — Intervall in Sekunden (Standard 14400 = 4 Stunden)
- INSTAGRAM_PROFILE_URL — z. B. https://www.instagram.com/heimatfront24_7official/#
- INSTAGRAM_COOKIE — sensibel; nur wenn nötig (z. B. sessionid=...)
- USER_AGENT — falls du einen speziellen UA setzen willst (Standard ist mobiler UA)
- LOG_LEVEL — INFO oder DEBUG (für Fehlersuche)

Beispiel (.env-Inhalt als Text)
DISCORD_TOKEN=YOUR_DISCORD_BOT_TOKEN
GUILD_ID=123456789012345678
CHANNEL_ID=987654321098765432
INSTAGRAM_USERNAME=heimatfront24_7official
INSTAGRAM_PROFILE_URL=https://www.instagram.com/heimatfront24_7official/#
UPDATE_INTERVAL=14400
LOG_LEVEL=INFO

5) Bot starten
- python bot.py

Beim Start verbindet sich der Bot mit Discord und der Update-Task beginnt gemäß UPDATE_INTERVAL.

Fehlerbehebung / Tipps
- Meldung "Keine Instagram-Zahl ermittelt" oder JSON-Antwort {"message":"useragent mismatch","status":"fail"}:
  - Setze LOG_LEVEL=DEBUG in .env und starte den Bot neu, um detaillierte HTTP‑Logs zu sehen.
  - Probiere, USER_AGENT in .env auf einen mobilen Instagram-User-Agent zu setzen (Standard ist bereits mobil).
  - Wenn weiterhin "useragent mismatch" erscheint, setze optional INSTAGRAM_COOKIE mit einem gültigen sessionid (nur für dein Konto, sensibel!).
- Testbefehle mit curl (zum Debuggen, ersetze <user> und setze passenden User-Agent):
  - curl -s -A "mobile UA" -H "X-IG-App-ID: 936619743392459" "https://i.instagram.com/api/v1/users/web_profile_info/?username=<user>"
  - curl -s -A "mobile UA" "https://www.instagram.com/<user>/?__a=1&__d=dis"
- Wenn Instagram 403/429/CAPTCHA liefert: wahrscheinlich Block/Rate-Limit. Erhöhe UPDATE_INTERVAL, verwende Browser-basierte Lösungen (Playwright/Puppeteer) oder einen professionellen Scraping-Service.
- Profil privat oder nicht existent: es wird keine Zahl gefunden.

Sicherheit & Legal
- Speichere DISCORD_TOKEN und ggf. INSTAGRAM_COOKIE sicher (nicht in öffentlichen Repositories).
- Prüfe die Nutzungsbedingungen von Instagram und TikTok. Scraping ist auf eigenes Risiko.

Verbesserungsmöglichkeiten / nächste Schritte
- Nutzung der offiziellen APIs (Instagram Graph API) für zuverlässige Daten (erfordert Business/Creator Account + App-Setup).
- Browser‑basierte Scraper (Playwright/Puppeteer) zur besseren Handhabung von JS-Rendering und CAPTCHAs.
- Dockerfile / systemd Unit zum einfachen Deployment.
- Separate Update-Intervalle pro Plattform oder History‑Logging der Änderungen.
- Testskript hinzufügen, das einmalig die Rohantwort der INSTAGRAM_PROFILE_URL ausgibt (hilft beim Debuggen).

Wenn du möchtest
- Ich kann .env.example erweitern, ein test_instagram_fetch.py hinzufügen oder eine Playwright-Version schreiben. Sage kurz, welche Erweiterung du möchtest.