#!/usr/bin/env python3
"""
Discord bot: aktualisiert Channel(s) mit aktuellen Followerzahlen von TikTok und/oder Instagram (Scraping).
Konfigurierbar: TikTok und/oder Instagram aktivieren; separate Channel-IDs möglich.

WARNUNG:
- Scraping ist anfällig für Änderungen, CAPTCHAs und ggf. gegen ToS der Plattformen.
- Verwende die Lösung sparsam (Default-Intervall = 4 Stunden).
"""
import os
import re
import json
import logging
from typing import Optional

import aiohttp
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("social-follower-bot")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

# Allgemeiner Fallback-Channel (optional). Wird verwendet, wenn keine separate Plattform-Channel-ID gesetzt ist.
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

# Optionale separate Channel-IDs pro Plattform (überschreiben CHANNEL_ID)
CHANNEL_ID_TIKTOK = int(os.getenv("CHANNEL_ID_TIKTOK", "0"))
CHANNEL_ID_INSTAGRAM = int(os.getenv("CHANNEL_ID_INSTAGRAM", "0"))

# Plattform-Benutzernamen (ohne @)
TIKTOK_USERNAME = os.getenv("TIKTOK_USERNAME", "").lstrip("@")
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "").lstrip("@")

# Aktivierung per ENV (true/false). Wenn nicht gesetzt, werden Plattformen aktiviert, wenn ein Username gesetzt ist.
def parse_bool_env(name: str, default: Optional[bool] = None) -> bool:
    v = os.getenv(name)
    if v is None:
        return default if default is not None else False
    return v.strip().lower() in ("1", "true", "yes", "y", "on")

ENABLE_TIKTOK = parse_bool_env("ENABLE_TIKTOK", default=(bool(TIKTOK_USERNAME)))
ENABLE_INSTAGRAM = parse_bool_env("ENABLE_INSTAGRAM", default=(bool(INSTAGRAM_USERNAME)))

# Update-Intervall (Sekunden). Default 4 Stunden = 14400 Sekunden
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", str(4 * 3600)))

# HTTP User-Agent
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                                      "Chrome/120.0.0.0 Safari/537.36")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


async def fetch_page(session: aiohttp.ClientSession, url: str, headers: dict = None, timeout: int = 20) -> str:
    h = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    if headers:
        h.update(headers)
    async with session.get(url, headers=h, timeout=timeout) as resp:
        text = await resp.text(errors="ignore")
        if resp.status != 200:
            logger.debug("GET %s returned %s", url, resp.status)
        return text


#
# TikTok scraping (same strategies as before)
#
def extract_tiktok_from_sigi_state(html: str) -> Optional[int]:
    m = re.search(r'<script[^>]*id=["\']SIGI_STATE["\'][^>]*>(.*?)</script>', html, re.S | re.I)
    if not m:
        return None
    try:
        raw = m.group(1).strip()
        data = json.loads(raw)
    except Exception:
        return None

    um = data.get("UserModule") or data.get("userModule") or {}
    users = um.get("users") or um.get("userList") or {}
    for v in users.values():
        if isinstance(v, dict):
            stats = v.get("stats")
            if stats and "followerCount" in stats:
                try:
                    return int(stats["followerCount"])
                except Exception:
                    continue
    return None


def extract_tiktok_by_regex(html: str) -> Optional[int]:
    m = re.search(r'"followerCount"\s*:\s*([0-9]{1,15})', html)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    m2 = re.search(r'([\d.,]+)\s*Followers', html, re.I)
    if m2:
        raw = m2.group(1).replace(",", "").replace(".", "")
        try:
            return int(raw)
        except Exception:
            return None
    return None


async def fetch_tiktok_followers(session: aiohttp.ClientSession, username: str) -> int:
    if not username:
        raise RuntimeError("TIKTOK_USERNAME nicht gesetzt")

    url = f"https://www.tiktok.com/@{username}"
    html = await fetch_page(session, url)

    count = extract_tiktok_from_sigi_state(html)
    if count is not None:
        return count

    count = extract_tiktok_by_regex(html)
    if count is not None:
        return count

    html2 = await fetch_page(session, f"https://www.tiktok.com/@{username}?lang=en")
    count = extract_tiktok_from_sigi_state(html2) or extract_tiktok_by_regex(html2)
    if count is not None:
        return count

    node_url = f"https://www.tiktok.com/node/share/user/@{username}"
    try:
        async with session.get(node_url, headers={"User-Agent": USER_AGENT}, timeout=10) as resp:
            if resp.status == 200:
                try:
                    j = await resp.json()
                    for path in [
                        ("user", "stats", "followerCount"),
                        ("userInfo", "stats", "followerCount"),
                        ("userInfo", "user", "stats", "followerCount"),
                    ]:
                        cur = j
                        for p in path:
                            if isinstance(cur, dict) and p in cur:
                                cur = cur[p]
                            else:
                                cur = None
                                break
                        if isinstance(cur, int):
                            return int(cur)
                except Exception:
                    pass
    except Exception:
        pass

    raise RuntimeError("TikTok: Followerzahl nicht gefunden (Scraping failed).")


#
# Instagram scraping
#
async def fetch_instagram_followers(session: aiohttp.ClientSession, username: str) -> int:
    if not username:
        raise RuntimeError("INSTAGRAM_USERNAME nicht gesetzt")

    # Strategy 1: JSON endpoint (may or may not work)
    json_url = f"https://www.instagram.com/{username}/?__a=1&__d=dis"
    try:
        async with session.get(json_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=10) as resp:
            if resp.status == 200:
                try:
                    j = await resp.json()
                    cur = j
                    for k in ("graphql", "user", "edge_followed_by", "count"):
                        if isinstance(cur, dict) and k in cur:
                            cur = cur[k]
                        else:
                            cur = None
                            break
                    if isinstance(cur, int):
                        return int(cur)
                except Exception:
                    pass
    except Exception:
        pass

    # Strategy 2: profile page regex
    url = f"https://www.instagram.com/{username}/"
    html = await fetch_page(session, url)
    m = re.search(r'"edge_followed_by"\s*:\s*\{\s*"count"\s*:\s*([0-9]{1,15})', html)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass

    # Strategy 3: window._sharedData
    m2 = re.search(r'window\._sharedData\s*=\s*({.*?});</script>', html, re.S)
    if m2:
        try:
            d = json.loads(m2.group(1))
            for path in [
                ("entry_data", "ProfilePage", 0, "graphql", "user", "edge_followed_by", "count"),
            ]:
                cur = d
                ok = True
                for p in path:
                    if isinstance(p, int):
                        try:
                            cur = cur[p]
                        except Exception:
                            ok = False
                            break
                    else:
                        if isinstance(cur, dict) and p in cur:
                            cur = cur[p]
                        else:
                            ok = False
                            break
                if ok and isinstance(cur, int):
                    return int(cur)
        except Exception:
            pass

    raise RuntimeError("Instagram: Followerzahl nicht gefunden (Scraping failed).")


def format_text_single(platform: str, count: int) -> str:
    if platform.lower() == "tiktok":
        return f"TikTok: {count:,} Followers"
    if platform.lower() == "instagram":
        return f"Instagram: {count:,} Followers"
    return f"{platform}: {count:,} Followers"


def format_combined_text(t_count: Optional[int], i_count: Optional[int]) -> str:
    parts = []
    if t_count is not None:
        parts.append(f"TikTok: {t_count:,} Followers")
    if i_count is not None:
        parts.append(f"Instagram: {i_count:,} Followers")
    if not parts:
        return "Followers: unknown"
    text = " | ".join(parts)
    if len(text) > 90:
        short = []
        if t_count is not None:
            short.append(f"TT:{t_count:,}")
        if i_count is not None:
            short.append(f"IG:{i_count:,}")
        text = " | ".join(short)
    return text


async def update_channel_by_id(channel_id: int, new_text: str):
    if channel_id <= 0:
        logger.debug("Ungültige channel_id: %s", channel_id)
        return
    guild = bot.get_guild(GUILD_ID) if GUILD_ID else None
    if not guild:
        logger.warning("Guild nicht gefunden (GUILD_ID fehlt oder Bot nicht auf Server).")
        return
    channel = guild.get_channel(channel_id)
    if not channel:
        logger.warning("Channel nicht gefunden (ID: %s).", channel_id)
        return
    try:
        if isinstance(channel, discord.TextChannel):
            await channel.edit(topic=new_text)
            logger.info("Text-Channel topic aktualisiert (ID %s) -> %s", channel_id, new_text)
        else:
            await channel.edit(name=new_text)
            logger.info("Channel name aktualisiert (ID %s) -> %s", channel_id, new_text)
    except Exception as e:
        logger.exception("Fehler beim Ändern des Channels (ID %s): %s", channel_id, e)


@tasks.loop(seconds=UPDATE_INTERVAL)
async def update_follower_count():
    await bot.wait_until_ready()
    async with aiohttp.ClientSession() as session:
        t_count = None
        i_count = None

        # Fetch enabled platforms
        if ENABLE_TIKTOK:
            if not TIKTOK_USERNAME:
                logger.warning("ENABLE_TIKTOK=true aber TIKTOK_USERNAME leer. Überspringe TikTok.")
            else:
                try:
                    t_count = await fetch_tiktok_followers(session, TIKTOK_USERNAME)
                    logger.info("TikTok followers: %s", t_count)
                except Exception as e:
                    logger.warning("TikTok fetch failed: %s", e)

        if ENABLE_INSTAGRAM:
            if not INSTAGRAM_USERNAME:
                logger.warning("ENABLE_INSTAGRAM=true aber INSTAGRAM_USERNAME leer. Überspringe Instagram.")
            else:
                try:
                    i_count = await fetch_instagram_followers(session, INSTAGRAM_USERNAME)
                    logger.info("Instagram followers: %s", i_count)
                except Exception as e:
                    logger.warning("Instagram fetch failed: %s", e)

        # Decide target channels and update
        # If both platforms enabled and both map to same channel (or only CHANNEL_ID), write combined text.
        # Otherwise update platform-specific channels separately.
        # Resolve platform channel ids with precedence: PLATFORM_CHANNEL_ID -> CHANNEL_ID -> 0 (skip)
        t_channel = CHANNEL_ID_TIKTOK or CHANNEL_ID
        i_channel = CHANNEL_ID_INSTAGRAM or CHANNEL_ID

        # Both enabled and channel ids equal and >0 -> combined update
        if (ENABLE_TIKTOK and ENABLE_INSTAGRAM) and (t_channel > 0 and i_channel > 0) and (t_channel == i_channel):
            # If neither count found -> skip
            if t_count is None and i_count is None:
                logger.warning("Keine Follower-Zahlen ermittelt für beide Plattformen. Skip update.")
                return
            new_text = format_combined_text(t_count, i_count)
            await update_channel_by_id(t_channel, new_text)
            return

        # Otherwise update each enabled platform in its channel (if channel id valid)
        if ENABLE_TIKTOK and t_channel > 0:
            if t_count is None:
                logger.warning("Keine TikTok-Zahl ermittelt, überspringe TikTok-Update.")
            else:
                await update_channel_by_id(t_channel, format_text_single("tiktok", t_count))

        if ENABLE_INSTAGRAM and i_channel > 0:
            if i_count is None:
                logger.warning("Keine Instagram-Zahl ermittelt, überspringe Instagram-Update.")
            else:
                await update_channel_by_id(i_channel, format_text_single("instagram", i_count))


@bot.event
async def on_ready():
    logger.info("Bot eingeloggt als %s (ID: %s)", bot.user, bot.user.id)
    if not update_follower_count.is_running():
        update_follower_count.start()


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN nicht gesetzt. Beende.")
        raise SystemExit(1)
    bot.run(DISCORD_TOKEN)