# bot.py  –  ClothesBot  (i18n refactor)
# Language: English default, 100+ languages via translations.py
# DB column required: manager_user.language  (VARCHAR, default 'en')

import asyncio
import logging
import os
import re
import random
import string
import time

import requests
from telegram import (
    Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)

from script.database import (
    get_user, create_user, update_user_field,
    get_user_by_username, get_all_users,
    log_image_creation, log_video_creation,
    get_image_count, get_video_count,
    get_total_spent, get_referral_stats,
    check_and_do_rollcall, get_key, use_key,
    get_queue_count, increment_queue, decrement_queue,
)
from translations import (
    t, lang_keyboard, get_lang_name,
    LANGUAGES, DEFAULT_LANG,
)

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN        = os.getenv("BOT_TOKEN", "")
CHANNEL_ID       = os.getenv("CHANNEL_ID", "@your_channel")
CHANNEL_LINK     = os.getenv("CHANNEL_LINK", "https://t.me/your_channel")
ADMIN_IDS        = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
BYPASS_LINK      = os.getenv("BYPASS_LINK", "https://example.com/bypass")
REFERRAL_BOT_URL = os.getenv("REFERRAL_BOT_URL", "https://t.me/YourBot?start=")

COST_IMAGE  = int(os.getenv("COST_IMAGE", "20"))
COST_VIDEO  = int(os.getenv("COST_VIDEO", "30"))
MAX_QUEUE   = int(os.getenv("MAX_QUEUE", "5"))

PACKAGE_LABELS = {
    "free":    "🆓 FREE",
    "vip":     "👑 VIP",
    "vip_pro": "💎 VIP PRO",
}
ROLLCALL_REWARDS = {
    "free":    0,
    "vip":     1500,
    "vip_pro": 5000,
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_user_lang(uid: int | str) -> str:
    """Read language preference from DB. Falls back to DEFAULT_LANG."""
    try:
        u = get_user(str(uid))
        return (u.language or DEFAULT_LANG) if u else DEFAULT_LANG
    except Exception:
        return DEFAULT_LANG


def pkg_label(pkg: str) -> str:
    return PACKAGE_LABELS.get(pkg, pkg)


def badge_for(coins: int) -> str:
    if coins >= 50000: return "💎 Diamond"
    if coins >= 20000: return "🥇 Gold"
    if coins >= 5000:  return "🥈 Silver"
    return "🥉 Bronze"


async def check_channel_membership(bot: Bot, uid: int) -> bool:
    try:
        m = await bot.get_chat_member(CHANNEL_ID, uid)
        return m.status not in ("left", "kicked")
    except Exception:
        return False


# ── Keyboards ─────────────────────────────────────────────────────────────────

def kb_main(u, lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    pkg  = getattr(u, "package", "free")
    reward = ROLLCALL_REWARDS.get(pkg, 0)

    if pkg == "free":
        rc_btn = InlineKeyboardButton(t("btn_rollcall_upgrade", lang), callback_data="rollcall")
    elif getattr(u, "rollcall_done", False):
        rc_btn = InlineKeyboardButton(t("btn_rollcall_done", lang), callback_data="rollcall")
    else:
        rc_btn = InlineKeyboardButton(t("btn_rollcall_ready", lang, reward=reward), callback_data="rollcall")

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_create_image", lang), callback_data="create_image")],
        [InlineKeyboardButton(t("btn_create_video", lang), callback_data="create_video")],
        [
            InlineKeyboardButton(t("btn_wallet",    lang), callback_data="wallet"),
            InlineKeyboardButton(t("btn_buy_coins", lang), callback_data="buy_coins"),
        ],
        [
            InlineKeyboardButton(t("btn_external_link", lang), callback_data="external_link"),
            InlineKeyboardButton(t("btn_referral",      lang), callback_data="referral"),
        ],
        [
            InlineKeyboardButton(t("btn_stats", lang), callback_data="stats"),
            InlineKeyboardButton(t("btn_help",  lang), callback_data="help"),
        ],
        [
            InlineKeyboardButton(t("btn_language", lang), callback_data="language"),
            rc_btn,
        ],
    ])


def kb_back(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t("btn_back", lang), callback_data="home")
    ]])


def kb_cancel(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t("btn_cancel", lang), callback_data="home")
    ]])


def kb_after_image(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_make_video", lang), callback_data="video_from_last")],
        [
            InlineKeyboardButton(t("btn_new_image", lang), callback_data="create_image"),
            InlineKeyboardButton(t("btn_home",      lang), callback_data="home"),
        ],
    ])


def kb_after_video(coins: int, lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_coins_left", lang, coins=coins), callback_data="wallet")],
        [
            InlineKeyboardButton(t("btn_new_video", lang), callback_data="create_video"),
            InlineKeyboardButton(t("btn_home",      lang), callback_data="home"),
        ],
    ])


def kb_prompt_selector(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    presets = [
        ("👗 Dress",         "wear a beautiful dress, elegant"),
        ("👔 Suit",          "wearing a professional suit"),
        ("👙 Swimwear",      "wearing a swimsuit, beach"),
        ("🎌 Anime",         "anime style outfit, colorful"),
        ("🧥 Casual",        "casual outfit, modern streetwear"),
        ("✏️ Custom Prompt", "CUSTOM"),
    ]
    rows = []
    for label, value in presets:
        rows.append([InlineKeyboardButton(label, callback_data=f"preset_{value}")])
    rows.append([InlineKeyboardButton(t("btn_cancel", lang), callback_data="home")])
    return InlineKeyboardMarkup(rows)


# ── Splash / home screen ──────────────────────────────────────────────────────

async def animated_splash(bot: Bot, chat_id: int, u, lang: str = DEFAULT_LANG):
    coins  = getattr(u, "coins", 0)
    images = getattr(u, "image_count", 0)
    videos = getattr(u, "video_count", 0)
    pkg    = getattr(u, "package", "free")
    name   = getattr(u, "full_name", "User") or "User"
    reward = ROLLCALL_REWARDS.get(pkg, 0)

    lines = [
        t("splash_greeting",   lang, name=name),
        "",
        t("splash_account",    lang),
        t("splash_coins",      lang, coins=coins),
        t("splash_images",     lang, images=images),
        t("splash_videos",     lang, videos=videos),
        "└──────────────────────────┘",
        "",
        t("splash_cost_image", lang, cost=COST_IMAGE),
        t("splash_cost_video", lang, cost=COST_VIDEO),
        "",
        t("splash_earn_hint",  lang),
        "",
        t("splash_choose",     lang),
    ]

    msg = await bot.send_message(
        chat_id, "⏳ Loading\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    for i in range(1, len(lines) + 1):
        await asyncio.sleep(0.08)
        await msg.edit_text(
            "\n".join(lines[:i]),
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    # roll-call hint
    if pkg == "free":
        hint = t("splash_rc_free", lang)
    elif getattr(u, "rollcall_done", False):
        hint = t("splash_rc_done", lang)
    else:
        hint = t("splash_rc_pending", lang, reward=reward)

    final = "\n".join(lines) + f"\n\n{hint}"
    await msg.edit_text(
        final,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=kb_main(u, lang),
    )


async def splash_final(bot: Bot, chat_id: int, u, lang: str = DEFAULT_LANG):
    """Quick (non-animated) home screen."""
    coins  = getattr(u, "coins", 0)
    images = getattr(u, "image_count", 0)
    videos = getattr(u, "video_count", 0)
    pkg    = getattr(u, "package", "free")
    name   = getattr(u, "full_name", "User") or "User"
    reward = ROLLCALL_REWARDS.get(pkg, 0)

    if pkg == "free":
        hint = t("splash_rc_free", lang)
    elif getattr(u, "rollcall_done", False):
        hint = t("splash_rc_done", lang)
    else:
        hint = t("splash_rc_pending", lang, reward=reward)

    text = "\n".join([
        t("splash_greeting",   lang, name=name),
        "",
        t("splash_account",    lang),
        t("splash_coins",      lang, coins=coins),
        t("splash_images",     lang, images=images),
        t("splash_videos",     lang, videos=videos),
        "└──────────────────────────┘",
        "",
        t("splash_cost_image", lang, cost=COST_IMAGE),
        t("splash_cost_video", lang, cost=COST_VIDEO),
        "",
        t("splash_earn_hint",  lang),
        "",
        t("splash_choose",     lang),
        "",
        hint,
    ])
    await bot.send_message(
        chat_id, text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=kb_main(u, lang),
    )


# ── Wallet / balance message ──────────────────────────────────────────────────

async def msg_balance(bot: Bot, chat_id: int, u, lang: str = DEFAULT_LANG):
    coins  = getattr(u, "coins", 0)
    images = getattr(u, "image_count", 0)
    videos = getattr(u, "video_count", 0)
    spent  = getattr(u, "total_spent", 0)
    name   = getattr(u, "full_name", "User") or "User"
    uid    = getattr(u, "telegram_id", "?")

    text = "\n".join([
        t("balance_title",   lang),
        "",
        t("balance_name",    lang, name=name),
        t("balance_id",      lang, uid=uid),
        "",
        t("balance_header",  lang),
        t("balance_coins",   lang, coins=coins),
        "└──────────────────────────┘",
        "",
        t("balance_history", lang),
        t("balance_images",  lang, images=images),
        t("balance_videos",  lang, videos=videos),
        t("balance_spent",   lang, spent=spent),
        "└──────────────────────────┘",
    ])
    await bot.send_message(
        chat_id, text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=kb_back(lang),
    )


# ── Stats message ─────────────────────────────────────────────────────────────

async def msg_stats(bot: Bot, chat_id: int, u, lang: str = DEFAULT_LANG):
    coins  = getattr(u, "coins", 0)
    images = getattr(u, "image_count", 0)
    videos = getattr(u, "video_count", 0)
    spent  = getattr(u, "total_spent", 0)
    pkg    = getattr(u, "package", "free")
    uid    = getattr(u, "telegram_id", "?")

    text = "\n".join([
        t("stats_title",        lang),
        "",
        t("stats_id",           lang, uid=uid),
        t("stats_rank",         lang, badge=badge_for(coins), pkg=pkg_label(pkg)),
        "",
        t("stats_coins_header", lang),
        t("stats_current",      lang, coins=coins),
        t("stats_spent",        lang, spent=spent),
        "└──────────────────────────┘",
        "",
        t("stats_activity",     lang),
        t("stats_images",       lang, images=images),
        t("stats_videos",       lang, videos=videos),
        "└──────────────────────────┘",
    ])
    await bot.send_message(
        chat_id, text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=kb_back(lang),
    )


# ── Help message ──────────────────────────────────────────────────────────────

async def msg_help(bot: Bot, chat_id: int, lang: str = DEFAULT_LANG):
    text = "\n".join([
        t("help_title",          lang),
        "",
        t("help_image_title",    lang, cost=COST_IMAGE),
        t("help_image_steps",    lang),
        "",
        t("help_video_title",    lang, cost=COST_VIDEO),
        t("help_video_steps",    lang),
        "",
        t("help_checkin_title",  lang),
        t("help_checkin_free",   lang),
        t("help_checkin_vip",    lang),
        t("help_checkin_vippro", lang),
        t("help_checkin_reset",  lang),
        "",
        t("help_coins_title",    lang),
        t("help_coins_1",        lang),
        t("help_coins_2",        lang),
        t("help_coins_3",        lang),
        t("help_coins_4",        lang),
        "",
        t("help_vip_title",      lang),
        t("help_vip_steps",      lang),
    ])
    await bot.send_message(
        chat_id, text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=kb_back(lang),
    )


# ── Join channel prompt ───────────────────────────────────────────────────────

async def send_join_prompt(bot: Bot, chat_id: int, lang: str = DEFAULT_LANG):
    text = "\n".join([
        t("join_title",   lang),
        "",
        t("join_warning", lang),
        "",
        t("join_step1",   lang),
        t("join_step2",   lang),
        t("join_step3",   lang),
    ])
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_join_channel", lang), url=CHANNEL_LINK)],
        [InlineKeyboardButton(t("btn_joined",       lang), callback_data="check_join")],
    ])
    await bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)


# ── Processing log helpers ────────────────────────────────────────────────────

async def render_log_step(msg, lines: list[str], lang: str = DEFAULT_LANG):
    """Edit a message to show accumulated log lines."""
    await msg.edit_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def render_video_log(msg, lines: list[str], elapsed: int, lang: str = DEFAULT_LANG):
    text = "\n".join(lines) + f"\n\n  ⏱️ Elapsed: {elapsed}s"
    try:
        await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception:
        pass


# ── /start command ────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg  = update.effective_user
    uid = str(tg.id)
    lang = get_user_lang(uid)

    # Channel membership check
    if not await check_channel_membership(context.bot, tg.id):
        await send_join_prompt(context.bot, tg.id, lang)
        return

    # Register / load user
    u = get_user(uid)
    if not u:
        ref_id = None
        if context.args:
            arg = context.args[0]
            if arg.startswith("ref_"):
                ref_id = arg[4:]

        u = create_user(
            telegram_id=uid,
            username=tg.username or "",
            full_name=tg.full_name or "",
            referrer_id=ref_id,
            language=DEFAULT_LANG,
        )

        # Notify referrer
        if ref_id:
            referrer = get_user(ref_id)
            if referrer:
                r_lang = get_user_lang(ref_id)
                await context.bot.send_message(
                    int(ref_id),
                    "\n".join([
                        t("ref_inviter_success",  r_lang),
                        t("ref_inviter_newuser",  r_lang, name=tg.full_name or tg.username or uid),
                        t("ref_inviter_reward",   r_lang, reward=500),
                        t("ref_inviter_balance",  r_lang, coins=getattr(referrer, "coins", 0) + 500),
                    ]),
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            await context.bot.send_message(
                tg.id,
                "\n".join([
                    t("ref_invitee_welcome", lang),
                    t("ref_invitee_joined",  lang),
                    t("ref_invitee_reward",  lang, reward=500),
                    t("ref_invitee_added",   lang),
                    "",
                    t("ref_invitee_start",   lang),
                ]),
                parse_mode=ParseMode.MARKDOWN_V2,
            )

    lang = get_user_lang(uid)
    await animated_splash(context.bot, tg.id, u, lang)


# ── Callback query handler ────────────────────────────────────────────────────

async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    await q.answer()
    d    = q.data
    uid  = str(q.from_user.id)
    lang = get_user_lang(uid)
    u    = get_user(uid)

    # ── Home
    if d == "home":
        u = get_user(uid)
        await splash_final(context.bot, q.message.chat_id, u, lang)
        return

    # ── Channel join check
    if d == "check_join":
        if await check_channel_membership(context.bot, q.from_user.id):
            u = get_user(uid) or create_user(
                telegram_id=uid,
                username=q.from_user.username or "",
                full_name=q.from_user.full_name or "",
                language=DEFAULT_LANG,
            )
            await splash_final(context.bot, q.message.chat_id, u, lang)
        else:
            await q.answer(t("join_not_yet", lang), show_alert=True)
        return

    # ── Language picker
    if d == "language":
        text = t("lang_title", lang) + "\n\n" + t("lang_subtitle", lang)
        await context.bot.send_message(
            q.message.chat_id, text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=lang_keyboard(lang),
        )
        return

    if d.startswith("lang_set_"):
        new_lang = d[len("lang_set_"):]
        if new_lang in LANGUAGES:
            update_user_field(uid, "language", new_lang)
            lang = new_lang
            u    = get_user(uid)
            lang_display = get_lang_name(new_lang)
            await q.answer(t("lang_changed", lang, lang=lang_display))
            await splash_final(context.bot, q.message.chat_id, u, lang)
        return

    # ── Wallet
    if d == "wallet":
        await msg_balance(context.bot, q.message.chat_id, u, lang)
        return

    # ── Buy coins (external link placeholder)
    if d == "buy_coins":
        await context.bot.send_message(
            q.message.chat_id,
            "💳 Contact admin to purchase coins or VIP\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=kb_back(lang),
        )
        return

    # ── Stats
    if d == "stats":
        await msg_stats(context.bot, q.message.chat_id, u, lang)
        return

    # ── Help
    if d == "help":
        await msg_help(context.bot, q.message.chat_id, lang)
        return

    # ── External link / bypass
    if d == "external_link":
        text = "\n".join([
            t("key_title",  lang),
            "",
            t("key_step1",  lang),
            t("key_step2",  lang),
            t("key_step3",  lang),
            "",
            t("key_reward", lang),
        ])
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_get_key",    lang), url=BYPASS_LINK)],
            [InlineKeyboardButton(t("btn_cancel_key", lang), callback_data="home")],
        ])
        await context.bot.send_message(
            q.message.chat_id, text,
            parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb,
        )
        return

    # ── Referral
    if d == "referral":
        ref_link = f"{REFERRAL_BOT_URL}ref_{uid}"
        stats = get_referral_stats(uid)
        count  = stats.get("count", 0)
        earned = stats.get("earned", 0)
        text = "\n".join([
            t("ref_title",          lang),
            "",
            t("ref_your_link",      lang),
            f"`{ref_link}`",
            "",
            t("ref_reward_header",  lang),
            t("ref_reward_you",     lang, reward=500),
            t("ref_reward_friend",  lang, bonus=200),
            "└──────────────────────────┘",
            "",
            t("ref_stats_header",   lang),
            t("ref_invited",        lang, count=count),
            t("ref_earned",         lang, earned=earned),
            "└──────────────────────────┘",
            "",
            t("ref_how_title",      lang),
            t("ref_how_steps",      lang, reward=500),
        ])
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_share_link", lang), url=f"https://t.me/share/url?url={ref_link}")],
            [InlineKeyboardButton(t("btn_back",       lang), callback_data="home")],
        ])
        await context.bot.send_message(
            q.message.chat_id, text,
            parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb,
        )
        return

    # ── Roll-call / check-in
    if d == "rollcall":
        pkg    = getattr(u, "package", "free")
        reward = ROLLCALL_REWARDS.get(pkg, 0)

        if pkg == "free":
            text = "\n".join([
                t("rc_vip_only_title", lang),
                "",
                t("rc_vip_only_free",  lang),
                t("rc_vip_only_vip",   lang),
                t("rc_vip_only_pro",   lang),
                "",
                t("rc_free_hint",      lang),
                "",
                t("rc_upgrade_hint",   lang),
            ])
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_upgrade_vip", lang), callback_data="buy_coins")],
                [InlineKeyboardButton(t("btn_earn_link",   lang), callback_data="external_link")],
                [InlineKeyboardButton(t("btn_invite",      lang), callback_data="referral")],
                [InlineKeyboardButton(t("btn_back",        lang), callback_data="home")],
            ])
            await context.bot.send_message(
                q.message.chat_id, text,
                parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb,
            )
            return

        result = check_and_do_rollcall(uid)
        if result == "already":
            await q.answer(t("rc_already", lang, reward=reward), show_alert=True)
            return

        new_coins = getattr(get_user(uid), "coins", 0)
        text = "\n".join([
            t("rc_success_title",  lang),
            "",
            t("rc_success_pkg",    lang, pkg=pkg_label(pkg)),
            t("rc_success_reward", lang, reward=reward),
            t("rc_success_bal",    lang, coins=new_coins),
            "",
            t("rc_success_hint",   lang),
        ])
        await context.bot.send_message(
            q.message.chat_id, text,
            parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb_back(lang),
        )
        return

    # ── Create image
    if d == "create_image":
        coins = getattr(u, "coins", 0)
        if coins < COST_IMAGE:
            text = "\n".join([
                t("img_no_coins_title", lang),
                "",
                t("img_no_coins_body",  lang, cost=COST_IMAGE, coins=coins, diff=COST_IMAGE - coins),
                "",
                t("img_no_coins_hint",  lang),
            ])
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_upgrade_vip", lang), callback_data="buy_coins")],
                [InlineKeyboardButton(t("btn_earn_link",   lang), callback_data="external_link")],
                [InlineKeyboardButton(t("btn_back",        lang), callback_data="home")],
            ])
            await context.bot.send_message(
                q.message.chat_id, text,
                parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb,
            )
            return

        # Queue check
        if get_queue_count() >= MAX_QUEUE:
            await context.bot.send_message(
                q.message.chat_id,
                t("queue_full", lang),
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=kb_back(lang),
            )
            return

        after = coins - COST_IMAGE
        text = "\n".join([
            t("img_start_title",   lang),
            "",
            t("img_start_balance", lang, coins=coins, cost=COST_IMAGE, after=after),
            "",
            t("img_start_step",    lang),
        ])
        context.user_data["state"] = "awaiting_image_photo"
        await context.bot.send_message(
            q.message.chat_id, text,
            parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb_cancel(lang),
        )
        return

    # ── Create video (standalone)
    if d == "create_video":
        coins = getattr(u, "coins", 0)
        if coins < COST_VIDEO:
            text = "\n".join([
                t("vid_no_coins_title", lang),
                "",
                t("vid_no_coins_body",  lang, cost=COST_VIDEO, coins=coins),
                "",
                t("vid_no_coins_hint",  lang),
            ])
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_upgrade_vip", lang), callback_data="buy_coins")],
                [InlineKeyboardButton(t("btn_back",        lang), callback_data="home")],
            ])
            await context.bot.send_message(
                q.message.chat_id, text,
                parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb,
            )
            return

        after = coins - COST_VIDEO
        text = "\n".join([
            t("vid_start_title",   lang),
            "",
            t("vid_start_balance", lang, coins=coins, cost=COST_VIDEO, after=after),
            "",
            t("vid_start_step",    lang),
        ])
        context.user_data["state"] = "awaiting_video_photo"
        await context.bot.send_message(
            q.message.chat_id, text,
            parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb_cancel(lang),
        )
        return

    # ── Create video from last image
    if d == "video_from_last":
        last_image = context.user_data.get("last_image_url")
        if not last_image:
            await context.bot.send_message(
                q.message.chat_id,
                t("vid_no_last_image", lang),
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=kb_back(lang),
            )
            return

        coins = getattr(u, "coins", 0)
        if coins < COST_VIDEO:
            text = "\n".join([
                t("vid_no_coins_title", lang),
                "",
                t("vid_no_coins_body", lang, cost=COST_VIDEO, coins=coins),
                "",
                t("vid_no_coins_hint", lang),
            ])
            await context.bot.send_message(
                q.message.chat_id, text,
                parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb_back(lang),
            )
            return

        after = coins - COST_VIDEO
        text = "\n".join([
            t("vid_from_last_title",   lang),
            "",
            t("vid_from_last_balance", lang, cost=COST_VIDEO, after=after),
            "",
            t("vid_from_last_step",    lang),
        ])
        context.user_data["state"] = "awaiting_video_prompt_from_last"
        await context.bot.send_message(
            q.message.chat_id, text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t("btn_cancel", lang), callback_data="home")
            ]]),
        )
        return

    # ── Preset prompt selection
    if d.startswith("preset_"):
        value = d[len("preset_"):]
        photo_file_id = context.user_data.get("pending_photo_file_id")
        if not photo_file_id:
            await context.bot.send_message(
                q.message.chat_id,
                t("preset_no_photo", lang),
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=kb_back(lang),
            )
            return

        if value == "CUSTOM":
            text = "\n".join([
                t("img_prompt_title", lang),
                "",
                t("img_prompt_hint",  lang),
                "",
                t("img_prompt_type",  lang),
            ])
            context.user_data["state"] = "awaiting_custom_prompt"
            await context.bot.send_message(
                q.message.chat_id, text,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(t("btn_cancel", lang), callback_data="home")
                ]]),
            )
            return

        await q.answer(t("preset_processing", lang))
        await do_image_generation(context.bot, q.message.chat_id, uid, photo_file_id, value, context, lang)
        return


# ── Message handler ───────────────────────────────────────────────────────────

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg   = update.effective_user
    uid  = str(tg.id)
    lang = get_user_lang(uid)
    state = context.user_data.get("state", "")
    msg  = update.message

    # ── KEY redemption (any state)
    if msg.text and re.match(r'^KEY_[A-Z0-9]{8,}$', msg.text.strip()):
        key_record = get_key(msg.text.strip())
        if not key_record or key_record.used:
            await msg.reply_text(t("key_invalid", lang), parse_mode=ParseMode.MARKDOWN_V2)
        else:
            use_key(msg.text.strip(), uid)
            await msg.reply_text(t("key_success", lang), parse_mode=ParseMode.MARKDOWN_V2)
        return

    # ── Waiting for photo (image flow)
    if state == "awaiting_image_photo":
        if not msg.photo:
            await msg.reply_text(t("img_no_photo", lang), parse_mode=ParseMode.MARKDOWN_V2)
            return
        photo_file_id = msg.photo[-1].file_id
        context.user_data["pending_photo_file_id"] = photo_file_id
        context.user_data["state"] = "awaiting_prompt"

        text = "\n".join([
            t("img_got_photo",    lang),
            "",
            t("img_choose_style", lang),
            t("img_choose_hint",  lang),
        ])
        await msg.reply_text(
            text, parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=kb_prompt_selector(lang),
        )
        return

    # ── Waiting for photo (video flow)
    if state == "awaiting_video_photo":
        if not msg.photo:
            await msg.reply_text(t("vid_no_photo", lang), parse_mode=ParseMode.MARKDOWN_V2)
            return
        photo_file_id = msg.photo[-1].file_id
        context.user_data["pending_video_photo_file_id"] = photo_file_id
        context.user_data["state"] = "awaiting_video_prompt"

        text = "\n".join([
            t("vid_got_photo",       lang),
            "",
            t("vid_prompt_step",     lang),
            "",
            t("vid_prompt_examples", lang),
        ])
        await msg.reply_text(
            text, parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=kb_cancel(lang),
        )
        return

    # ── Custom image prompt
    if state == "awaiting_custom_prompt":
        if not msg.text:
            return
        prompt = msg.text.strip()
        photo_file_id = context.user_data.get("pending_photo_file_id")
        if not photo_file_id:
            await msg.reply_text(t("img_no_photo", lang), parse_mode=ParseMode.MARKDOWN_V2)
            return
        context.user_data["state"] = ""
        await do_image_generation(context.bot, msg.chat_id, uid, photo_file_id, prompt, context, lang)
        return

    # ── Video prompt
    if state in ("awaiting_video_prompt", "awaiting_video_prompt_from_last"):
        if not msg.text:
            return
        prompt = msg.text.strip()
        context.user_data["state"] = ""

        if state == "awaiting_video_prompt_from_last":
            photo_url = context.user_data.get("last_image_url")
            await do_video_generation_from_url(context.bot, msg.chat_id, uid, photo_url, prompt, context, lang)
        else:
            photo_file_id = context.user_data.get("pending_video_photo_file_id")
            if not photo_file_id:
                await msg.reply_text(t("vid_no_photo", lang), parse_mode=ParseMode.MARKDOWN_V2)
                return
            await do_video_generation(context.bot, msg.chat_id, uid, photo_file_id, prompt, context, lang)
        return


# ── Image generation ──────────────────────────────────────────────────────────

async def do_image_generation(
    bot: Bot, chat_id: int, uid: str,
    photo_file_id: str, prompt: str,
    context: ContextTypes.DEFAULT_TYPE,
    lang: str = DEFAULT_LANG,
):
    u = get_user(uid)
    if getattr(u, "coins", 0) < COST_IMAGE:
        coins = getattr(u, "coins", 0)
        text = "\n".join([
            t("img_no_coins_title", lang),
            "",
            t("img_no_coins_body",  lang, cost=COST_IMAGE, coins=coins, diff=COST_IMAGE - coins),
        ])
        await bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb_back(lang))
        return

    increment_queue()
    update_user_field(uid, "coins", getattr(u, "coins", 0) - COST_IMAGE)

    log_msg = await bot.send_message(
        chat_id, t("queue_checking", lang),
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    lines = [
        t("proc_starting",   lang),
        t("proc_prompt",     lang, prompt=prompt),
    ]
    await render_log_step(log_msg, lines, lang)
    await asyncio.sleep(1)

    try:
        file = await bot.get_file(photo_file_id)
        photo_url = file.file_path
        lines.append(t("proc_photo_ready", lang))
        await render_log_step(log_msg, lines, lang)
        await asyncio.sleep(1)

        lines.append(t("proc_analyzing", lang))
        await render_log_step(log_msg, lines, lang)

        # ── Call your image API here ──────────────────────────────────────────
        # result_url = your_image_api(photo_url, prompt)
        # For scaffold, we use a placeholder:
        result_url = photo_url   # replace with actual API call
        # ─────────────────────────────────────────────────────────────────────

        await asyncio.sleep(2)

        new_coins = getattr(get_user(uid), "coins", 0)
        log_image_creation(uid, prompt)
        context.user_data["last_image_url"] = result_url

        await log_msg.delete()
        caption = "\n".join([
            t("img_result_title", lang),
            "",
            t("img_result_ok",    lang, prompt=prompt, coins=new_coins),
            "",
            t("img_result_hint",  lang),
        ])
        await bot.send_photo(
            chat_id, result_url,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=kb_after_image(lang),
        )

    except Exception as e:
        logger.error(f"Image generation error: {e}")
        update_user_field(uid, "coins", getattr(get_user(uid), "coins", 0) + COST_IMAGE)
        text = "\n".join([
            t("img_fail_title", lang),
            "",
            t("img_fail_body",  lang, error=str(e), cost=COST_IMAGE),
        ])
        await log_msg.edit_text(
            text, parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t("btn_img_start", lang), callback_data="create_image"),
                InlineKeyboardButton(t("btn_home",      lang), callback_data="home"),
            ]]),
        )
    finally:
        decrement_queue()


# ── Video generation ──────────────────────────────────────────────────────────

async def do_video_generation(
    bot: Bot, chat_id: int, uid: str,
    photo_file_id: str, prompt: str,
    context: ContextTypes.DEFAULT_TYPE,
    lang: str = DEFAULT_LANG,
):
    try:
        file = await bot.get_file(photo_file_id)
        photo_url = file.file_path
    except Exception as e:
        await bot.send_message(
            chat_id, t("vid_no_photo", lang),
            parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb_back(lang),
        )
        return
    await do_video_generation_from_url(bot, chat_id, uid, photo_url, prompt, context, lang)


async def do_video_generation_from_url(
    bot: Bot, chat_id: int, uid: str,
    photo_url: str, prompt: str,
    context: ContextTypes.DEFAULT_TYPE,
    lang: str = DEFAULT_LANG,
):
    u = get_user(uid)
    if getattr(u, "coins", 0) < COST_VIDEO:
        coins = getattr(u, "coins", 0)
        text = "\n".join([
            t("vid_no_coins_title", lang),
            "",
            t("vid_no_coins_body",  lang, cost=COST_VIDEO, coins=coins),
        ])
        await bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb_back(lang))
        return

    increment_queue()
    update_user_field(uid, "coins", getattr(u, "coins", 0) - COST_VIDEO)

    log_msg = await bot.send_message(
        chat_id, t("queue_checking", lang),
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    lines = [
        t("proc_video_starting", lang),
        t("proc_video_warning",  lang),
        t("proc_prompt",         lang, prompt=prompt),
    ]
    await render_log_step(log_msg, lines, lang)

    try:
        lines.append(t("proc_photo_ready2", lang))
        await render_log_step(log_msg, lines, lang)

        lines.append(t("proc_video_init", lang))
        await render_log_step(log_msg, lines, lang)

        start = time.time()

        # ── Call your video API here ──────────────────────────────────────────
        # Poll every 15s, update elapsed counter
        for _ in range(20):   # max ~5 min
            await asyncio.sleep(15)
            elapsed = int(time.time() - start)
            await render_video_log(log_msg, lines, elapsed, lang)
            # result_url = check_video_api_status(job_id)
            # if result_url: break
        result_url = photo_url  # placeholder – replace with actual
        # ─────────────────────────────────────────────────────────────────────

        new_coins = getattr(get_user(uid), "coins", 0)
        log_video_creation(uid, prompt)

        await log_msg.delete()
        caption = "\n".join([
            t("vid_result_title", lang),
            "",
            t("vid_result_ok",    lang, prompt=prompt, coins=new_coins),
        ])
        await bot.send_video(
            chat_id, result_url,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=kb_after_video(new_coins, lang),
        )

    except Exception as e:
        logger.error(f"Video generation error: {e}")
        update_user_field(uid, "coins", getattr(get_user(uid), "coins", 0) + COST_VIDEO)
        text = "\n".join([
            t("vid_fail_title", lang),
            "",
            t("vid_fail_body",  lang, error=str(e), cost=COST_VIDEO),
        ])
        await log_msg.edit_text(
            text, parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t("btn_vid_start", lang), callback_data="create_video"),
                InlineKeyboardButton(t("btn_home",      lang), callback_data="home"),
            ]]),
        )
    finally:
        decrement_queue()


# ── Admin commands ────────────────────────────────────────────────────────────

async def cmd_addcoins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    lang = get_user_lang(uid)
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text(t("admin_no_perm", lang))
        return
    if len(context.args) < 2:
        await update.message.reply_text(t("admin_addcoins_usage", lang), parse_mode=ParseMode.MARKDOWN_V2)
        return
    username = context.args[0].lstrip("@")
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text(t("admin_not_integer", lang), parse_mode=ParseMode.MARKDOWN_V2)
        return
    target = get_user_by_username(username)
    if not target:
        await update.message.reply_text(
            t("admin_user_notfound", lang, user=username),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    new_bal = getattr(target, "coins", 0) + amount
    update_user_field(str(target.telegram_id), "coins", new_bal)
    await update.message.reply_text(
        t("admin_addcoins_ok", lang, amount=amount, user=username, coins=new_bal),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def cmd_setpackage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    lang = get_user_lang(uid)
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text(t("admin_no_perm", lang))
        return
    if len(context.args) < 2:
        await update.message.reply_text(t("admin_setpkg_usage", lang), parse_mode=ParseMode.MARKDOWN_V2)
        return
    username = context.args[0].lstrip("@")
    pkg      = context.args[1].lower()
    if pkg not in ("free", "vip", "vip_pro"):
        await update.message.reply_text(t("admin_setpkg_invalid", lang), parse_mode=ParseMode.MARKDOWN_V2)
        return
    target = get_user_by_username(username)
    if not target:
        await update.message.reply_text(
            t("admin_user_notfound", lang, user=username),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    update_user_field(str(target.telegram_id), "package", pkg)
    await update.message.reply_text(
        t("admin_setpkg_ok", lang, user=username, pkg=pkg_label(pkg)),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def cmd_userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    lang = get_user_lang(uid)
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text(t("admin_no_perm", lang))
        return
    if not context.args:
        await update.message.reply_text(t("admin_userinfo_usage", lang), parse_mode=ParseMode.MARKDOWN_V2)
        return
    username = context.args[0].lstrip("@")
    target   = get_user_by_username(username)
    if not target:
        await update.message.reply_text(
            t("admin_user_notfound", lang, user=username),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    await update.message.reply_text(
        t("admin_userinfo_body", lang,
          user=username,
          uid=target.telegram_id,
          coins=getattr(target, "coins", 0),
          badge=badge_for(getattr(target, "coins", 0)),
          pkg=pkg_label(getattr(target, "package", "free")),
          images=getattr(target, "image_count", 0),
          videos=getattr(target, "video_count", 0),
          rollcall=getattr(target, "rollcall_done", False),
          language=getattr(target, "language", DEFAULT_LANG),
        ),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow users to open the language picker via /language command."""
    uid  = str(update.effective_user.id)
    lang = get_user_lang(uid)
    text = t("lang_title", lang) + "\n\n" + t("lang_subtitle", lang)
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=lang_keyboard(lang),
    )


# ── Application setup ─────────────────────────────────────────────────────────

def setup_application() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("language",   cmd_language))
    app.add_handler(CommandHandler("addcoins",   cmd_addcoins))
    app.add_handler(CommandHandler("setpackage", cmd_setpackage))
    app.add_handler(CommandHandler("userinfo",   cmd_userinfo))

    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_message))

    return app


if __name__ == "__main__":
    application = setup_application()
    application.run_polling(drop_pending_updates=True)