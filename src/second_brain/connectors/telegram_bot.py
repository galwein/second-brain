"""Telegram bot for mobile personal note capture."""
import logging
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from second_brain.config import get_config
from second_brain.connectors.base import BaseConnector
from second_brain.models import Item, ItemMeta
from second_brain.storage.base import BaseStorage

logger = logging.getLogger("second-brain.connectors.telegram")


class TelegramBotConnector(BaseConnector):
    """Telegram bot that captures personal notes into the Second Brain inbox.

    Supported commands:
        /note <text>  — Save a text note
        /link <url>   — Save a link for later processing
        /status       — Check inbox status
        /help         — Show available commands

    Also accepts plain text messages as notes.
    """

    def __init__(self, storage: BaseStorage | None = None):
        super().__init__(name="Telegram", target_store="personal")
        self._config = get_config()
        self._storage = storage
        self._app: Application | None = None
        self._items_captured: int = 0

    def _is_allowed(self, user_id: int) -> bool:
        """Check if a Telegram user is allowed to use the bot."""
        allowed = self._config.telegram.allowed_users
        return not allowed or user_id in allowed

    async def authenticate(self) -> bool:
        """Initialize the Telegram bot application."""
        try:
            token = self._config.telegram.bot_token
            if not token:
                logger.error("Telegram bot token not configured.")
                return False

            self._app = (
                Application.builder()
                .token(token)
                .build()
            )

            # Register handlers
            self._app.add_handler(CommandHandler("start", self._cmd_start))
            self._app.add_handler(CommandHandler("help", self._cmd_help))
            self._app.add_handler(CommandHandler("note", self._cmd_note))
            self._app.add_handler(CommandHandler("link", self._cmd_link))
            self._app.add_handler(CommandHandler("status", self._cmd_status))
            self._app.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text)
            )

            logger.info("Telegram bot initialized.")
            return True

        except Exception as e:
            logger.error(f"Telegram bot init failed: {e}")
            return False

    async def start_polling(self) -> None:
        """Start the bot in polling mode (blocking)."""
        if not self._app:
            raise RuntimeError("Bot not initialized. Call authenticate() first.")
        logger.info("Starting Telegram bot polling...")
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()

    async def stop(self) -> None:
        """Stop the bot."""
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    async def fetch_new_items(self, days_back: int = 7) -> list[Item]:
        """Not used for Telegram — items are captured in real-time via bot handlers."""
        return []

    async def get_status(self) -> dict:
        """Get Telegram bot status."""
        return {
            "connector": "Telegram Bot",
            "authenticated": self._app is not None,
            "target_store": self.target_store,
            "items_captured": self._items_captured,
            "bot_token_configured": bool(self._config.telegram.bot_token),
            "allowed_users": len(self._config.telegram.allowed_users),
        }

    # -- Bot handlers -------------------------------------------------------

    async def _save_note(self, title: str, content: str, tags: list[str], source_detail: str = "") -> str:
        """Save a note to the personal store inbox."""
        if not self._storage:
            return "❌ Storage not configured for Telegram bot."

        item = Item(
            meta=ItemMeta(
                title=title,
                source="telegram",
                store="personal",
                category="Inbox",
                tags=["telegram"] + tags,
                created=datetime.now(),
                updated=datetime.now(),
            ),
            content=content,
        )

        path = await self._storage.write_item(item)
        self._items_captured += 1
        return f"✅ Saved to inbox: {path}"

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update.effective_user.id):
            await update.message.reply_text("⛔ You are not authorized to use this bot.")
            return
        await update.message.reply_text(
            "🧠 **Second Brain Bot**\n\n"
            "Send me notes, links, or ideas and I'll save them to your personal Second Brain inbox.\n\n"
            "Commands:\n"
            "/note <text> — Save a note\n"
            "/link <url> — Save a link\n"
            "/status — Check inbox status\n"
            "/help — Show this help\n\n"
            "Or just send plain text — I'll save it as a note!",
            parse_mode="Markdown",
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update.effective_user.id):
            return
        await update.message.reply_text(
            "📋 **Commands:**\n"
            "/note <text> — Save a text note\n"
            "/link <url> — Save a link\n"
            "/status — Items in inbox\n"
            "/help — This help message\n\n"
            "💡 Just send plain text to quickly capture a thought!",
            parse_mode="Markdown",
        )

    async def _cmd_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update.effective_user.id):
            return
        text = " ".join(context.args) if context.args else ""
        if not text:
            await update.message.reply_text("Usage: /note <your note text>")
            return

        title = text.split("\n")[0][:80]
        result = await self._save_note(title=title, content=text, tags=["note"])
        await update.message.reply_text(result)

    async def _cmd_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update.effective_user.id):
            return
        if not context.args:
            await update.message.reply_text("Usage: /link <url> [optional description]")
            return

        url = context.args[0]
        description = " ".join(context.args[1:]) if len(context.args) > 1 else ""
        title = description or f"Link: {url[:60]}"
        content = f"**URL:** {url}\n\n{description}" if description else f"**URL:** {url}"

        result = await self._save_note(title=title, content=content, tags=["link", "bookmark"])
        await update.message.reply_text(result)

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update.effective_user.id):
            return

        if self._storage:
            from second_brain.models import ParaCategory
            inbox_items = await self._storage.list_items(category=ParaCategory.INBOX)
            count = len(inbox_items)
            await update.message.reply_text(
                f"📬 **Inbox Status:**\n"
                f"Items in inbox: {count}\n"
                f"Items captured this session: {self._items_captured}",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text("Storage not connected.")

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle plain text messages as quick notes."""
        if not self._is_allowed(update.effective_user.id):
            return
        text = update.message.text
        if not text:
            return
        title = text.split("\n")[0][:80]
        result = await self._save_note(title=title, content=text, tags=["quick-note"])
        await update.message.reply_text(result)
