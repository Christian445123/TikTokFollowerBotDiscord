#!/usr/bin/env python3
"""
Discord bot: aktualisiert Channel(s) mit Followerzahlen (TikTok, Instagram).
Beachtet:
 - Discord API (edits nur bei Änderung, permission checks, retry/backoff, per-channel throttle)
 - Externe API Rate Limits (Retry-After, per-service min interval, request retries/backoff)
Konfiguration über Umgebungsvariablen (.env)
"""
from __future__ import annotations

import os
import re
import json
import time
import logging
import asyncio
from typing import Optional, Dict, Any, Tuple

import aiohttp
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv
from urllib.parse import urlparse, urlunparse

load_dotenv()

# ---------------- Configuration (env) ----------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("social-follower-bot")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
CHANNEL_ID_INSTAGRAM = int(os.getenv("CHANNEL_ID_INSTAGRAM", "0"))
CHANNEL_ID_TIKTOK = int(os.getenv("CHANNEL_ID_TIKTOK", "0"))

TIKTOK_USERNAME = os.getenv("TIKTOK_USERNAME", "").lstrip("@")
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "").lstrip("@")
INSTAGRAM_PROFILE_URL = os.getenv("INSTAGRAM_PROFILE_URL", "").strip()
INSTAGRAM_COOKIE = os.getenv("INSTAGRAM_COOKIE", "")

USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
)

def _parse_bool_env(name: str, default: Optional[bool] = None) -> bool:
    v = os.getenv(name)
    if v is None:
        return default if default is not None else False
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")

ENABLE_TIKTOK = _parse_bool_env("ENABLE_TIKTOK", default=bool(TIKTOK_USERNAME))
ENABLE_INSTAGRAM = _parse_bool_env("ENABLE_INSTAGRAM", default=bool(INSTAGRAM_USERNAME or INSTAGRAM_PROFILE_URL))

UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", str(4 * 3600)))  # default 4 hours
MIN_UPDATE_SECONDS = int(os.getenv("MIN_UPDATE_SECONDS", "60"))
EDIT_MAX_RETRIES = int(os.getenv("EDIT_MAX_RETRIES", "3"))
EDIT_BACKOFF_BASE = float(os.getenv("EDIT_BACKOFF_BASE", "2.0"))
MAX_CONCURRENT_EDITS = int(os.getenv("MAX_CONCURRENT_EDITS", "2"))

# External API rate-limit config
EXTERNAL_MAX_RETRIES = int(os.getenv("EXTERNAL_MAX_RETRIES", "3"))
EXTERNAL_BACKOFF_BASE = float(os.getenv("EXTERNAL_BACKOFF_BASE", "2.0"))
EXTERNAL_MAX_CONCURRENT_REQUESTS = int(os.getenv("EXTERNAL_MAX_CONCURRENT_REQUESTS", "3"))

# Minimum interval between calls to each external service (seconds)
INSTAGRAM_MIN_INTERVAL = int(os.getenv("INSTAGRAM_MIN_INTERVAL", "300"))  # default 5 minutes
TIKTOK_MIN_INTERVAL = int(os.getenv("TIKTOK_MIN_INTERVAL", "300"))

# ---------------- Bot and state ----------------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

_last_update_ts: Dict[int, float] = {}          # per-channel last edit timestamp
_last_external_ts: Dict[str, float] = {}        # per-service last request timestamp, e.g. "instagram", "tiktok"
_edit_semaphore = asyncio.Semaphore(MAX_CONCURRENT_EDITS)
_external_semaphore = asyncio.Semaphore(EXTERNAL_MAX_CONCURRENT_REQUESTS)


# ---------------- Utilities: external request with retry & Retry-After handling ----------------
async def request_with_retries(
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Any] = None,
    timeout: int = 15,
    service_name: Optional[str] = None,
) -> Tuple[int, str, Dict[str, str]]:
    """
    Perform an HTTP request with retries and handling of 429 Retry-After.
    Returns (status, text, headers_dict).
    Raises RuntimeError on unrecoverable failure.
    """
    attempt = 0
    backoff = 1.0
    last_exc = None

    async with _external_semaphore:
        while attempt <= EXTERNAL_MAX_RETRIES:
            attempt += 1
            try:
                logger.debug("External request attempt %s: %s %s", attempt, method.upper(), url)
                resp = await session.request(method, url, headers=headers, params=params, json=json_data, timeout=timeout)
                status = resp.status
                text = await resp.text(errors="ignore")
                hdrs = dict(resp.headers)
                # Success
                if status in (200, 201):
                    return status, text, hdrs
                # Handle 429 with Retry-After
                if status == 429:
                    ra = hdrs.get("Retry-After") or hdrs.get("retry-after")
                    if ra:
                        try:
                            wait = float(ra)
                        except Exception:
                            wait = backoff * EXTERNAL_BACKOFF_BASE
                    else:
                        wait = backoff * EXTERNAL_BACKOFF_BASE
                    logger.warning(
                        "Received 429 from %s (%s). Waiting %.1fs before retry (attempt %s/%s).",
                        service_name or url,
                        url,
                        wait,
                        attempt,
                        EXTERNAL_MAX_RETRIES,
                    )
                    await asyncio.sleep(wait)
                    backoff *= EXTERNAL_BACKOFF_BASE
                    continue
                # Retry on 5xx
                if 500 <= status < 600:
                    wait = backoff * EXTERNAL_BACKOFF_BASE
                    logger.warning(
                        "Received %s from %s. Sleeping %.1fs and retrying (attempt %s/%s).",
                        status,
                        url,
                        wait,
                        attempt,
                        EXTERNAL_MAX_RETRIES,
                    )
                    await asyncio.sleep(wait)
                    backoff *= EXTERNAL_BACKOFF_BASE
                    continue
                # For other statuses treat as unrecoverable (400/401/403)
                raise RuntimeError(f"Request to {url} returned status {status}: {text[:300]}")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                last_exc = e
                wait = backoff * EXTERNAL_BACKOFF_BASE
                logger.debug("External request error (%s): %s. Sleeping %.1fs before retry.", url, e, wait)
                await asyncio.sleep(wait)
                backoff *= EXTERNAL_BACKOFF_BASE
        # exhausted retries
        raise RuntimeError(f"External request to {url} failed after {EXTERNAL_MAX_RETRIES} retries. Last error: {last_exc}")


# ---------------- External scrapers (rate-aware) ----------------
async def _throttle_service(service_key: str, min_interval: int):
    """Ensure min_interval between calls to a named service."""
    now = time.time()
    last = _last_external_ts.get(service_key, 0)
    since = now - last
    if since < min_interval:
        to_sleep = min_interval - since
        logger.info("Throttling service %s: sleeping %.1fs to respect min interval", service_key, to_sleep)
        await asyncio.sleep(to_sleep)
    _last_external_ts[service_key] = time.time()


async def fetch_instagram_followers(session: aiohttp.ClientSession, username: str,
                                    profile_url_override: Optional[str] = None) -> int:
    """Fetch Instagram follower count honoring rate limits and Retry-After."""
    if not username and not profile_url_override:
        raise RuntimeError("INSTAGRAM_USERNAME oder INSTAGRAM_PROFILE_URL muss gesetzt sein")

    await _throttle_service("instagram", INSTAGRAM_MIN_INTERVAL)

    cookie = INSTAGRAM_COOKIE or ""
    mobile_ua = USER_AGENT

    # 1) i.instagram.com endpoint
    if username:
        i_api = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
        headers_api = {
            "User-Agent": mobile_ua,
            "Referer": f"https://www.instagram.com/{username}/",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-IG-App-ID": "936619743392459",
        }
        if cookie:
            headers_api["Cookie"] = cookie
        try:
            status, text, hdrs = await request_with_retries(session, "GET", i_api, headers=headers_api, service_name="instagram")
            try:
                j = json.loads(text)
                for path in (("data", "user", "edge_followed_by", "count"),
                             ("user", "edge_followed_by", "count")):
                    cur = j
                    ok = True
                    for p in path:
                        if isinstance(cur, dict) and p in cur:
                            cur = cur[p]
                        else:
                            ok = False
                            break
                    if ok and isinstance(cur, int):
                        return int(cur)
            except Exception:
                logger.debug("i.instagram.com: JSON parse failed or unexpected structure")
        except Exception as e:
            logger.debug("i.instagram.com attempt error: %s", e)

    # 2) ?__a=1 endpoint
    if username:
        json_url = f"https://www.instagram.com/{username}/?__a=1&__d=dis"
        headers_json = {"User-Agent": mobile_ua, "Referer": f"https://www.instagram.com/{username}/", "X-IG-App-ID": "936619743392459"}
        if cookie:
            headers_json["Cookie"] = cookie
        try:
            status, text, hdrs = await request_with_retries(session, "GET", json_url, headers=headers_json, service_name="instagram")
            try:
                j = json.loads(text)
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
                logger.debug("?__a=1 parse failed or unexpected structure")
        except Exception as e:
            logger.debug("?__a=1 attempt error: %s", e)

    # 3) HTML fallback
    profile_url = ""
    if profile_url_override:
        try:
            p = urlparse(profile_url_override)
            p = p._replace(fragment="")
            profile_url = urlunparse(p)
        except Exception:
            profile_url = profile_url_override
    elif username:
        profile_url = f"https://www.instagram.com/{username}/"

    if profile_url:
        try:
            headers_html = {"Referer": "https://www.instagram.com/", "User-Agent": mobile_ua}
            if cookie:
                headers_html["Cookie"] = cookie
            status, html, hdrs = await request_with_retries(session, "GET", profile_url, headers=headers_html, service_name="instagram")
            m = re.search(r'"edge_followed_by"\s*:\s*\{\s*"count"\s*:\s*([0-9]{1,15})', html)
            if m:
                return int(m.group(1))
            m2 = re.search(r'window\._sharedData\s*=\s*({.*?});</script>', html, re.S)
            if m2:
                try:
                    d = json.loads(m2.group(1))
                    cur = d
                    for p in ("entry_data", "ProfilePage", 0, "graphql", "user", "edge_followed_by", "count"):
                        if isinstance(p, int):
                            try:
                                cur = cur[p]
                            except Exception:
                                cur = None
                                break
                        else:
                            if isinstance(cur, dict) and p in cur:
                                cur = cur[p]
                            else:
                                cur = None
                                break
                    if isinstance(cur, int):
                        return int(cur)
                except Exception:
                    logger.debug("window._sharedData parse failed")
            m3 = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
            if m3:
                try:
                    ld = json.loads(m3.group(1))
                    if isinstance(ld, dict):
                        stats = ld.get("interactionStatistic") or ld.get("mainEntityofPage")
                        if isinstance(stats, dict):
                            count = stats.get("userInteractionCount")
                            if isinstance(count, (int, str)):
                                return int(count)
                except Exception:
                    pass
        except Exception as e:
            logger.debug("HTML fallback error: %s", e)

    raise RuntimeError("Instagram: Followerzahl nicht gefunden (alle Strategien fehlgeschlagen).")


async def fetch_tiktok_followers(session: aiohttp.ClientSession, username: str) -> int:
    """Fetch TikTok follower count honoring rate limits."""
    if not username:
        raise RuntimeError("TIKTOK_USERNAME nicht gesetzt")

    await _throttle_service("tiktok", TIKTOK_MIN_INTERVAL)

    url = f"https://www.tiktok.com/@{username}"
    try:
        status, html, hdrs = await request_with_retries(session, "GET", url, headers={"User-Agent": USER_AGENT}, service_name="tiktok")
        # quick regex attempt
        m = re.search(r'"followerCount"\s*:\s*([0-9]{1,15})', html)
        if m:
            return int(m.group(1))
        m2 = re.search(r'([\d.,]+)\s*Followers', html, re.I)
        if m2:
            raw = m2.group(1).replace(",", "").replace(".", "")
            return int(raw)
    except Exception as e:
        logger.debug("TikTok profile page attempt failed: %s", e)

    # fallback to node/share endpoint
    node = f"https://www.tiktok.com/node/share/user/@{username}"
    try:
        status, text, hdrs = await request_with_retries(session, "GET", node, headers={"User-Agent": USER_AGENT}, service_name="tiktok")
        try:
            j = json.loads(text)
            for path in [("user", "stats", "followerCount"), ("userInfo", "stats", "followerCount")]:
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
            logger.debug("TikTok node response parse failed")
    except Exception as e:
        logger.debug("TikTok node endpoint attempt failed: %s", e)

    raise RuntimeError("TikTok: Followerzahl nicht gefunden.")


# ---------------- Discord-safe edit helpers ----------------
def _can_bot_manage_channel(guild: discord.Guild, channel: discord.abc.GuildChannel) -> bool:
    try:
        me = guild.me
        if me is None:
            me = guild.get_member(bot.user.id)
        if me is None:
            return False
        perms = channel.permissions_for(me)
        return perms.manage_channels
    except Exception:
        return False


async def safe_edit_channel_obj(channel: discord.abc.GuildChannel, new_name: Optional[str] = None,
                                new_topic: Optional[str] = None) -> bool:
    """
    Edit the channel only if a change is necessary.
    Returns True if edited or nothing to do, raises on unrecoverable error.
    """
    try:
        if isinstance(channel, discord.TextChannel):
            cur = channel.topic or ""
            if new_topic is None:
                return True
            if cur.strip() == new_topic.strip():
                logger.debug("No topic change needed for channel %s", channel.id)
                return True
            await channel.edit(topic=new_topic)
            logger.info("Updated topic for channel %s -> %s", channel.id, new_topic)
            return True
        else:
            cur = channel.name or ""
            if new_name is None:
                return True
            if cur.strip() == new_name.strip():
                logger.debug("No name change needed for channel %s", channel.id)
                return True
            await channel.edit(name=new_name)
            logger.info("Updated name for channel %s -> %s", channel.id, new_name)
            return True
    except discord.Forbidden:
        logger.error("Missing permissions to edit channel %s", getattr(channel, "id", "unknown"))
        raise
    except discord.NotFound:
        logger.warning("Channel not found when attempting edit: %s", getattr(channel, "id", "unknown"))
        raise
    except discord.HTTPException as e:
        logger.warning("HTTPException when editing channel %s: %s", getattr(channel, "id", "unknown"), e)
        raise


async def edit_with_retry(channel: discord.abc.GuildChannel, new_name: Optional[str] = None,
                          new_topic: Optional[str] = None, max_retries: int = EDIT_MAX_RETRIES) -> bool:
    """
    Wrap safe_edit_channel_obj with retry + exponential backoff.
    Respects semaphore to limit concurrent edits and per-channel throttle.
    """
    cid = getattr(channel, "id", 0)
    now = time.time()
    last_ts = _last_update_ts.get(cid, 0)
    if now - last_ts < MIN_UPDATE_SECONDS:
        logger.info("Skipping edit for channel %s: only %.1fs since last update (min %.1fs)", cid, now - last_ts, MIN_UPDATE_SECONDS)
        return False

    guild = channel.guild
    if not _can_bot_manage_channel(guild, channel):
        logger.error("Bot lacks Manage Channels permission for guild %s / channel %s", guild.id if guild else "?", cid)
        return False

    backoff = 1.0
    attempt = 0
    async with _edit_semaphore:
        while attempt <= max_retries:
            try:
                attempt += 1
                await safe_edit_channel_obj(channel, new_name=new_name, new_topic=new_topic)
                _last_update_ts[cid] = time.time()
                return True
            except discord.HTTPException as e:
                # try to extract retry-after from response headers if available
                retry_after = None
                try:
                    # discord.py surfaces rate limit handling but still may raise HTTPException
                    retry_after = float(getattr(e, "retry_after", 0) or 0)
                except Exception:
                    retry_after = None
                if retry_after and retry_after > 0:
                    logger.warning("Discord rate limited: sleeping %.1fs (retry-after)", retry_after)
                    await asyncio.sleep(retry_after)
                else:
                    sleep_for = backoff * EDIT_BACKOFF_BASE
                    logger.warning("Edit attempt %s failed; sleeping %.1fs before retry", attempt, sleep_for)
                    await asyncio.sleep(sleep_for)
                    backoff *= EDIT_BACKOFF_BASE
            except (discord.Forbidden, discord.NotFound) as e:
                logger.error("Unrecoverable error editing channel %s: %s", cid, e)
                return False
            except Exception as e:
                logger.warning("Unexpected error editing channel %s: %s", cid, e)
                sleep_for = backoff * EDIT_BACKOFF_BASE
                await asyncio.sleep(sleep_for)
                backoff *= EDIT_BACKOFF_BASE
        logger.error("Exceeded max retries editing channel %s", cid)
        return False


# ---------------- Update task ----------------
def format_text_single(platform: str, count: int) -> str:
    if platform.lower() == "tiktok":
        return f"TikTok: {count:,} Followers"
    if platform.lower() == "instagram":
        return f"Instagram: {count:,} Followers"
    return f"{platform}: {count:,} Followers"


@tasks.loop(seconds=UPDATE_INTERVAL)
async def update_follower_count():
    await bot.wait_until_ready()
    guild = bot.get_guild(GUILD_ID) if GUILD_ID else None
    if not guild:
        logger.warning("Guild not found (GUILD_ID missing or bot not on server).")
        return

    async with aiohttp.ClientSession() as session:
        # Instagram
        if ENABLE_INSTAGRAM:
            try:
                count = await fetch_instagram_followers(session, INSTAGRAM_USERNAME, profile_url_override=(INSTAGRAM_PROFILE_URL or None))
                logger.info("Instagram followers: %s", count)
                target_id = CHANNEL_ID_INSTAGRAM or CHANNEL_ID
                if target_id > 0:
                    channel = guild.get_channel(target_id)
                    if channel:
                        # For text channels we update topic; for voice channels update name
                        if isinstance(channel, discord.TextChannel):
                            await edit_with_retry(channel, new_topic=format_text_single("instagram", count))
                        else:
                            await edit_with_retry(channel, new_name=format_text_single("instagram", count))
                    else:
                        logger.warning("Instagram target channel %s not found.", target_id)
            except Exception as e:
                logger.warning("Instagram fetch failed: %s", e)

        # TikTok
        if ENABLE_TIKTOK:
            try:
                count = await fetch_tiktok_followers(session, TIKTOK_USERNAME)
                logger.info("TikTok followers: %s", count)
                target_id = CHANNEL_ID_TIKTOK or CHANNEL_ID
                if target_id > 0:
                    channel = guild.get_channel(target_id)
                    if channel:
                        if isinstance(channel, discord.TextChannel):
                            await edit_with_retry(channel, new_topic=format_text_single("tiktok", count))
                        else:
                            await edit_with_retry(channel, new_name=format_text_single("tiktok", count))
                    else:
                        logger.warning("TikTok target channel %s not found.", target_id)
            except Exception as e:
                logger.warning("TikTok fetch failed: %s", e)


@bot.event
async def on_ready():
    logger.info("Bot logged in as %s (ID: %s)", bot.user, bot.user.id)
    if not update_follower_count.is_running():
        update_follower_count.start()


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not set. Exiting.")
        raise SystemExit(1)
    bot.run(DISCORD_TOKEN)