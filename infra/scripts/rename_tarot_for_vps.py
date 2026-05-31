#!/usr/bin/env python3
"""Rename and stage tarot SVGs for VPS upload.

Source: c:\\Users\\Anton\\natal-chart-app\\public\\tarot\\{majors,minors}\\card-NN-kebab.svg
Target: /tmp/tarot_staged/NN_Title_Case_Name.svg

The target naming matches what backend serves at /static/tarot/{image_key}.
"""
import shutil
from pathlib import Path

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

SRC = Path(r"C:\Users\Anton\natal-chart-app\public\tarot")
DST = Path("/tmp/tarot_staged")


def target_name(idx: int) -> str:
    if idx < 22:
        return f"{idx:02d}_{MAJOR_ORDER[idx].replace(' ', '_')}.svg"
    minor_idx = idx - 22
    suit = SUIT_ORDER[minor_idx // 14]
    rank = RANK_ORDER[minor_idx % 14]
    return f"{idx:02d}_{rank}_of_{suit}.svg"


def main():
    DST.mkdir(parents=True, exist_ok=True)
    all_src = list(SRC.rglob("card-*.svg"))
    assert len(all_src) == 78, f"expected 78 SVGs, got {len(all_src)}"

    for p in sorted(all_src):
        idx = int(p.name.split("-", 2)[1])
        new_name = target_name(idx)
        shutil.copyfile(p, DST / new_name)
        print(f"{p.name}  ->  {new_name}")

    staged = list(DST.glob("*.svg"))
    print(f"\nStaged {len(staged)} files at {DST}")


if __name__ == "__main__":
    main()
