import asyncio
import logging
from typing import Optional, List
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User, SchoolMessage

logger = logging.getLogger(__name__)


async def get_class_recipients(session: AsyncSession, school: str, grade: str) -> List[User]:
    """Retrieve all active users for a specific school and grade."""
    query = (
        select(User)
        .where(
            User.school == school,
            User.grade == grade,
            User.is_active.is_(True)
        )
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def broadcast_to_class(
    bot: Bot,
    session: AsyncSession,
    sender: User,
    category: str,
    text_content: Optional[str] = None,
    photo_file_id: Optional[str] = None
) -> dict:
    """Broadcasts a message from class admin ONLY to students of the same school and grade.
    Returns stats: total, sent, failed.
    """
    recipients = await get_class_recipients(session, sender.school, sender.grade)
    
    # Save the message in history
    db_msg = SchoolMessage(
        sender_id=sender.id,
        school=sender.school,
        grade=sender.grade,
        category=category,
        text_content=text_content,
        photo_file_id=photo_file_id
    )
    session.add(db_msg)
    await session.commit()

    header = (
        f"🔔 <b>[{category.upper()}] от Администратора класса</b>\n"
        f"🏫 <b>{sender.school} | {sender.grade}</b>\n"
        f"👤 От: {sender.first_name} {sender.last_name}\n"
        f"────────────────────\n"
    )

    caption_or_text = header + (text_content if text_content else "")

    sent_count = 0
    fail_count = 0

    for i, user in enumerate(recipients):
        try:
            if photo_file_id:
                await bot.send_photo(
                    chat_id=user.telegram_id,
                    photo=photo_file_id,
                    caption=caption_or_text[:1024],
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=caption_or_text[:4096],
                    parse_mode="HTML"
                )
            sent_count += 1
        except TelegramForbiddenError:
            # User stopped or blocked the bot, mark inactive
            logger.warning(f"User {user.telegram_id} blocked bot. Marking inactive.")
            user.is_active = False
            fail_count += 1
        except TelegramRetryAfter as e:
            logger.warning(f"Flood limit reached. Sleeping for {e.retry_after} seconds.")
            await asyncio.sleep(e.retry_after)
            # Retry sending
            try:
                if photo_file_id:
                    await bot.send_photo(user.telegram_id, photo_file_id, caption=caption_or_text[:1024], parse_mode="HTML")
                else:
                    await bot.send_message(user.telegram_id, caption_or_text[:4096], parse_mode="HTML")
                sent_count += 1
            except Exception:
                fail_count += 1
        except TelegramAPIError as e:
            logger.error(f"Failed to send to user {user.telegram_id}: {e}")
            fail_count += 1
        except Exception as e:
            logger.error(f"Unexpected error sending to {user.telegram_id}: {e}")
            fail_count += 1

        # Prevent hitting Telegram rate limit: max ~25-30 messages per second
        if (i + 1) % 25 == 0:
            await asyncio.sleep(1.0)

    await session.commit()

    return {
        "total": len(recipients),
        "sent": sent_count,
        "failed": fail_count
    }
