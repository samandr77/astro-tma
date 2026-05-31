#!/usr/bin/env python3
"""
Update image_key for all tarot cards to match new custom image filenames.
Run: docker compose exec backend python scripts/update_image_keys.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import TarotCard

# Map name_en -> file index
MAJOR_ORDER = [
    "The Fool", "The Magician", "The High Priestess", "The Empress",
    "The Emperor", "The Hierophant", "The Lovers", "The Chariot",
    "Strength", "The Hermit", "Wheel of Fortune", "Justice",
    "The Hanged Man", "Death", "Temperance", "The Devil",
    "The Tower", "The Star", "The Moon", "The Sun",
    "Judgement", "The World",
]

SUIT_ORDER = ["Wands", "Cups", "Swords", "Pentacles"]
RANK_ORDER = [
    "Ace", "Two", "Three", "Four", "Five", "Six", "Seven",
    "Eight", "Nine", "Ten", "Page", "Knight", "Queen", "King",
]


def get_image_key(name_en: str) -> str:
    """Convert card name_en to image filename."""
    # Major arcana
    if name_en in MAJOR_ORDER:
        idx = MAJOR_ORDER.index(name_en)
        return f"{idx:02d}_{name_en.replace(' ', '_')}.svg"

    # Minor arcana: "Ace of Wands" -> index 22, etc.
    for suit_idx, suit in enumerate(SUIT_ORDER):
        if name_en.endswith(f"of {suit}"):
            rank = name_en.replace(f" of {suit}", "")
            if rank in RANK_ORDER:
                rank_idx = RANK_ORDER.index(rank)
                idx = 22 + suit_idx * 14 + rank_idx
                return f"{idx:02d}_{name_en.replace(' ', '_')}.svg"

    return None


async def update():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(TarotCard))
        cards = result.scalars().all()
        print(f"Found {len(cards)} cards")

        updated = 0
        for card in cards:
            key = get_image_key(card.name_en)
            if key:
                card.image_key = key
                updated += 1
                print(f"  {card.name_en} -> {key}")
            else:
                print(f"  WARNING: no key for {card.name_en}")

        await session.commit()
        print(f"\nUpdated {updated} image keys")


asyncio.run(update())
