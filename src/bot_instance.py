"""
Module-level Bot instance shared by main.py and scheduler.py.
Kept in its own file to avoid circular imports.
"""
import os
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from dotenv import load_dotenv
load_dotenv()

bot = Bot(
    token=os.getenv("BOT_TOKEN", ""),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
