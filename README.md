# Social Follower Discord Bot (TikTok + Instagram — Scraping)

Kurzbeschreibung  
Dieser Bot liest (per Scraping) öffentliche Profilseiten von Instagram und TikTok und aktualisiert einen oder mehrere Discord‑Channels mit aktuellen Followerzahlen. Er berücksichtigt Discord‑API‑Richtlinien (Rate‑Limits, Berechtigungen, Retry/Backoff) und versucht auch, externe API‑Rate‑Limits (Instagram/TikTok) zu respektieren.

Wichtige Hinweise
- Dies ist eine Scraping‑Lösung — keine offiziellen APIs. Scraping kann instabil sein (HTML/JSON‑Änderungen), CAPTCHAs auslösen oder durch Rate‑Limits/Blocking behindert werden.
- Verwende die Lösung sparsam (Standard‑Intervall = 4 Stunden). Für produktiven Einsatz sind offizielle APIs (Instagram Graph API, TikTok Open Platform) die zuverlässigere Alternative.
- Speichere sensible Werte (DISCORD_TOKEN, INSTAGRAM_COOKIE) sicher und niemals in öffentlichen Repositories.

Features
- Unterstützt Instagram und TikTok (einzeln oder gleichzeitig).
- Separate Channel‑IDs für Instagram und TikTok oder ein gemeinsamer Channel.
- Optional: nutze eine funktionierende Profil‑URL (z. B. `INSTAGRAM_PROFILE_URL`) als Fallback.
- Respektiert Discord‑API‑Regeln:
  - Editiere Channel nur, wenn sich der Name/Topic ändert.
  - Prüft Manage Channels‑Berechtigung vor Änderungen.
  - Exponentieller Backoff + Retry bei temporären Fehlern / 429.
  - Per‑Channel Throttle (MIN_UPDATE_SECONDS) und Semaphore zur Begrenzung paralleler Edits.
- Respektiert externe API Rate‑Limits:
  - Retry‑After Handling bei 429, Per‑Service Mindestintervalle (z. B. INSTAGRAM_MIN_INTERVAL).
  - Semaphore zur Begrenzung paralleler externen Requests.

Schnellstart (Schritt für Schritt)
1) Dateien
- Lege `bot.py`, `requirements.txt` und `.env.example` in ein Verzeichnis.
- Kopiere `.env.example` zu `.env` und passe die Werte an.

2) Python‑Umgebung
- Empfohlen: Python 3.10+
- Abhängigkeiten installieren:
  python -m pip install -r requirements.txt

3) Discord Bot erstellen und Berechtigungen
- Erstelle eine Anwendung in der Discord Developer Console und füge einen Bot hinzu.
- Gib dem Bot mindestens diese Berechtigungen (Scope/Bot): Manage Channels (wenn du Channel‑Name/Topic ändern möchtest). Alternativ: Send Messages wenn du stattdessen Nachrichten posten willst.
- Invite‑Link generieren und Bot auf Server hinzufügen.
- Developer Mode in Discord aktivieren (Einstellungen → Erweitert), um Server‑ und Channel‑IDs zu kopieren:
  - Server ID -> GUILD_ID
  - Channel ID(s) -> CHANNEL_ID, CHANNEL_ID_INSTAGRAM, CHANNEL_ID_TIKTOK

4) Konfiguration (.env)
- Kopiere `.env.example` nach `.env` und fülle die Werte aus.

Wichtige Umgebungsvariablen (Übersicht)
- DISCORD_TOKEN — Token deines Discord‑Bots (sensibel)
- GUILD_ID — Server/ Guild ID (Zahl)
- CHANNEL_ID — allgemeiner Fallback Channel ID (Zahl)
- CHANNEL_ID_INSTAGRAM — Channel ID nur für Instagram (überschreibt CHANNEL_ID für IG)
- CHANNEL_ID_TIKTOK — Channel ID nur für TikTok (überschreibt CHANNEL_ID für TT)
- INSTAGRAM_USERNAME — Instagram‑Benutzername (ohne @) (optional)
- INSTAGRAM_PROFILE_URL — alternative Profil‑URL z. B. https://www.instagram.com/heimatfront24_7official/# (optional; genutzt als HTML‑Fallback)
- INSTAGRAM_COOKIE — optional, sensibel (z. B. sessionid=...) falls Instagram blockt
- TIKTOK_USERNAME — TikTok‑Benutzername (ohne @) (optional)
- UPDATE_INTERVAL — Intervall zwischen vollständigen Poll‑Runs in Sekunden (Standard 14400 = 4 Stunden)
- MIN_UPDATE_SECONDS — minimaler Abstand zwischen Channel‑Edits pro Channel in Sekunden (Default 60)
- INSTAGRAM_MIN_INTERVAL — minimaler Abstand zwischen Instagram‑Requests in Sekunden (Default 300)
- TIKTOK_MIN_INTERVAL — minimaler Abstand zwischen TikTok‑Requests in Sekunden (Default 300)
- EXTERNAL_MAX_RETRIES — Anzahl Retries für externe Requests (Default 3)
- EXTERNAL_BACKOFF_BASE — Basisfaktor für externen Backoff (Default 2.0)
- EXTERNAL_MAX_CONCURRENT_REQUESTS — maximale parallele externe Requests (Default 3)
- EDIT_MAX_RETRIES — Anzahl Retries für Discord‑Channel‑Edits (Default 3)
- EDIT_BACKOFF_BASE — Basisfaktor für Edit‑Backoff (Default 2.0)
- MAX_CONCURRENT_EDITS — maximale parallele Channel‑Edits (Default 2)
- USER_AGENT — User‑Agent für externe Requests (Standard ist mobiler UA passend für Instagram)
- LOG_LEVEL — z. B. INFO oder DEBUG für detaillierte Logs

Beispiel `.env` (als Text)
DISCORD_TOKEN=YOUR_DISCORD_BOT_TOKEN  
GUILD_ID=123456789012345678  
CHANNEL_ID=987654321098765432  
INSTAGRAM_USERNAME=heimatfront24_7official  
INSTAGRAM_PROFILE_URL=https://www.instagram.com/heimatfront24_7official/#  
TIKTOK_USERNAME=dein_tiktok_name  
UPDATE_INTERVAL=14400  
MIN_UPDATE_SECONDS=60  
INSTAGRAM_MIN_INTERVAL=300  
TIKTOK_MIN_INTERVAL=300  
EXTERNAL_MAX_RETRIES=3  
EXTERNAL_BACKOFF_BASE=2.0  
EXTERNAL_MAX_CONCURRENT_REQUESTS=3  
EDIT_MAX_RETRIES=3  
EDIT_BACKOFF_BASE=2.0  
MAX_CONCURRENT_EDITS=2  
USER_AGENT=Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 ...  
LOG_LEVEL=INFO

Starten
python bot.py

Logs & Debugging
- Setze LOG_LEVEL=DEBUG für ausführliche HTTP‑ und Retry‑Logs (nur temporär).
- Bei Problemen mit Instagram: überprüfe die HTTP‑Responses (Status, Body) in den Logs. Häufige Fehler:
  - {"message":"useragent mismatch","status":"fail"} → Setze USER_AGENT auf einen mobilen UA oder nutze INSTAGRAM_COOKIE.
  - 403/429 → Block/Rate‑Limit; erhöhe INSTAGRAM_MIN_INTERVAL / UPDATE_INTERVAL.
- Test‑Requests lokal (curl) helfen beim Debugging:
  - curl -s -A "mobile UA" -H "X-IG-App-ID: 936619743392459" "https://i.instagram.com/api/v1/users/web_profile_info/?username=<user>"
  - curl -s -A "mobile UA" "https://www.instagram.com/<user>/?__a=1&__d=dis"

Discord‑API‑Best Practices (bereits umgesetzt)
- Channel nur editieren, wenn Name/Topic sich wirklich ändert (verringert API‑Calls).
- Vor Edit prüfen, ob Bot Manage Channels‑Berechtigung hat.
- Per‑Channel Throttle (MIN_UPDATE_SECONDS) schützt vor zu schnellen, wiederholten Edits.
- Exponentielles Backoff + Retry bei HTTP‑Fehlern & 429 (sowohl für Discord als auch für externe Requests).
- Semaphore zur Begrenzung paralleler Channel‑Edits und paralleler externen Requests.

Rate Limits der externen Dienste beachten
- Es gibt keine öffentliche, einheitliche Rate‑Limit‑Angabe für Instagram/TikTok‑Scraping; die implementierten MIN_INTERVALs und Retry‑Strategien dienen dazu, Blocking zu reduzieren.
- Empfehlung: halte INSTAGRAM_MIN_INTERVAL und TIKTOK_MIN_INTERVAL auf mindestens 300s (5 Minuten) für stabilen Betrieb; für Produktions‑Use Cases eher >= 900s (15 Minuten) oder nutze offizielle APIs.

Sicherheit & Legal
- Teile niemals DISCORD_TOKEN oder INSTAGRAM_COOKIE öffentlich.
- Lies die Terms of Service der Plattformen; Scraping kann gegen die AGB stehen. Verwende diese Lösung auf eigenes Risiko und vorzugsweise nur für Profile, deren Daten du verwaltest.

Verbesserungsmöglichkeiten / nächste Schritte
- Migration auf offizielle APIs:
  - Instagram Graph API (erfordert Business/Creator Account und Facebook Developer App).
  - TikTok Open Platform (erfordert App‑Registrierung / OAuth).
- Robusteres Scraping mit Headless Browser (Playwright/Puppeteer) bei persistierenden Blocks/CAPTCHAs.
- Persistentes Throttle‑State (z. B. in JSON/DB) damit Nachstarts Min‑Intervals beibehalten.
- Dockerfile / systemd Unit für einfaches Deployment.
- Optional: separate Update‑Intervalle pro Plattform, History‑Logging der Follower‑Entwicklung.

Support
- Wenn du möchtest, erstelle ich:
  - aktualisiertes `.env.example`,
  - ein kleines Testskript `test_instagram_fetch.py`, das einmal die Rohantwort der `INSTAGRAM_PROFILE_URL` anzeigt,
  - oder eine Playwright‑Version für stabileres Scraping.
Sag mir, welche Erweiterung du möchtest.