#!/usr/bin/env python3
"""
Discord bot: aktualisiert einen Channel-Name (voice) oder Topic (text) mit deiner aktuellen TikTok-Followerzahl.
Scraping-Lösung: liest die öffentliche TikTok-Profilseite und extrahiert followerCount.
WARNUNG: Scraping ist anfällig für Änderungen und ggf. gegen TikTok ToS.
"""
import os
import re
import json
import asyncio
import logging
from typing import Optional

import aiohttp
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tiktok-discord-bot")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
TIKTOK_USERNAME = os.getenv("TIKTOK_USERNAME", "").lstrip("@")
# Update-Intervall jetzt standardmäßig 4 Stunden = 14400 Sekunden
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", str(4 * 3600)))  # Sekunden
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                                      "Chrome/120.0.0.0 Safari/537.36")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


async def fetch_page(session: aiohttp.ClientSession, url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with session.get(url, headers=headers, timeout=20) as resp:
        text = await resp.text(errors="ignore")
        if resp.status != 200:
            logger.warning(f"GET {url} returned {resp.status}")
        return text


def extract_from_sigi_state(html: str) -> Optional[int]:
    """
    Versucht den JSON-Block <script id="SIGI_STATE">...</script> auszulesen
    und die followerCount zu finden.
    """
    m = re.search(r'<script[^>]*id=["\']SIGI_STATE["\'][^>]*>(.*?)</script>', html, re.S | re.I)
    if not m:
        return None
    try:
        raw = m.group(1).strip()
        data = json.loads(raw)
    except Exception as e:
        logger.debug("Fehler beim Parsen von SIGI_STATE JSON: %s", e)
        return None

    um = data.get("UserModule") or data.get("userModule") or {}
    users = um.get("users") or um.get("userList") or {}
    for k, v in users.items():
        stats = v.get("stats") if isinstance(v, dict) else None
        if stats and "followerCount" in stats:
            try:
                return int(stats["followerCount"])
            except Exception:
                continue
    return None


def extract_by_regex(html: str) -> Optional[int]:
    """
    Fallback: suche im HTML nach dem Pattern "followerCount":<number>
    """
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
    """
    Versucht mehrere Strategien, um followerCount eines öffentlichen Profils zu bekommen.
    Liefert int oder wirft RuntimeError.
    """
    if not username:
        raise RuntimeError("TIKTOK_USERNAME nicht gesetzt")

    url = f"https://www.tiktok.com/@{username}"
    html = await fetch_page(session, url)

    count = extract_from_sigi_state(html)
    if count is not None:
        return count

    count = extract_by_regex(html)
    if count is not None:
        return count

    html2 = await fetch_page(session, f"https://www.tiktok.com/@{username}?lang=en")
    count = extract_by_regex(html2) or extract_from_sigi_state(html2)
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

    raise RuntimeError("Followerzahl nicht gefunden (Scraping failed). Seite geändert oder blockiert.")


@tasks.loop(seconds=UPDATE_INTERVAL)
async def update_follower_count():
    await bot.wait_until_ready()
    guild = bot.get_guild(GUILD_ID) if GUILD_ID else None
    if not guild:
        logger.warning("Guild nicht gefunden (GUILD_ID fehlt oder Bot nicht auf Server).")
        return
    channel = guild.get_channel(CHANNEL_ID)
    if not channel:
        logger.warning("Channel nicht gefunden (CHANNEL_ID falsch oder Bot hat keinen Zugriff).")
        return

    async with aiohttp.ClientSession() as session:
        try:
            count = await fetch_tiktok_followers(session, TIKTOK_USERNAME)
            new_name = f"TikTok: {count:,} Follower"
            if isinstance(channel, discord.TextChannel):
                try:
                    await channel.edit(topic=new_name)
                    logger.info(f"Text-Channel topic aktualisiert -> {new_name}")
                except Exception as e:
                    logger.warning("Fehler beim Ändern des Topic: %s", e)
            else:
                try:
                    await channel.edit(name=new_name)
                    logger.info(f"Channel name aktualisiert -> {new_name}")
                except Exception as e:
                    logger.warning("Fehler beim Ändern des Channel-Namens: %s", e)
        except Exception as e:
            logger.exception("Fehler beim Abrufen/Aktualisieren der Followerzahl: %s", e)


@bot.event
async def on_ready():
    logger.info(f"Bot eingeloggt als {bot.user} (ID: {bot.user.id})")
    if not update_follower_count.is_running():
        update_follower_count.start()


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN nicht gesetzt. Beende.")
        raise SystemExit(1)
    bot.run(DISCORD_TOKEN)