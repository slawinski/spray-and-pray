"""Batch notifications for discovery results.

Only fires when new qualifying jobs were actually imported. Never emits
"0 new jobs" noise. Discord failures must not fail discovery.
"""

import logging

from cv_optimizer.config import settings

logger = logging.getLogger(__name__)


def _macos_notification(title: str, message: str) -> None:
    if not settings.enable_notifications:
        return
    try:
        import subprocess

        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{message}" with title "{title}"',
            ],
            check=False,
            timeout=10,
        )
    except Exception as exc:  # pragma: no cover — never fail discovery
        logger.warning("macOS notification failed: %s", exc)


def _discord_summary(imported: list[dict]) -> None:
    if not settings.enable_notifications:
        return
    webhook_url = settings.discord_webhook_url
    if not webhook_url:
        logger.info("Discord webhook not configured; skipping summary")
        return
    try:
        import requests

        count = len(imported)
        lines = [f"🎯 {count} new job matches"]
        for entry in imported[:10]:
            score = entry.get("score", "?")
            company = entry.get("company") or "?"
            role = entry.get("role") or "?"
            url = entry.get("url") or ""
            lines.append(f"{score}% — {company} — {role}")
            if url:
                lines.append(url)
        payload = {
            "content": None,
            "embeds": [
                {
                    "title": f"🎯 {count} new 85%+ job matches added",
                    "description": "\n".join(lines),
                    "color": 0x00FF00,
                }
            ],
        }
        requests.post(webhook_url, json=payload, timeout=10)
    except Exception as exc:
        logger.warning("Discord notification failed (discovery continues): %s", exc)


def notify_new_imports(imported: list[dict]) -> None:
    """Sends one batched notification; only when `imported` is non-empty."""
    if not imported:
        return
    count = len(imported)
    top = ", ".join(
        f"{e.get('score')} {e.get('company')} — {e.get('role')}"
        for e in imported[:3]
    )
    _macos_notification(
        "Spray and Pray",
        f"{count} new 85%+ job matches added",
    )
    logger.info("Notification: %d new qualifying Drafts (%s)", count, top)
    _discord_summary(imported)
