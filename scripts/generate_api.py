#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT_DIR / "docs"
CARDS_DIR = DOCS_DIR / "cards"
SEARCH_DIR = DOCS_DIR / "search"
SETS_DIR = DOCS_DIR / "sets"

SOURCE_OWNER = "PokemonTCG"
SOURCE_REPO = "pokemon-tcg-data"
USER_AGENT = "poketom-api-generator/1.0"
MAX_WORKERS = 12


def fetch_json(url: str, accept: str = "application/json") -> Any:
    request = Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def fetch_repo_metadata() -> dict[str, Any]:
    url = f"https://api.github.com/repos/{SOURCE_OWNER}/{SOURCE_REPO}"
    return fetch_json(url, accept="application/vnd.github+json")


def raw_url(branch: str, relative_path: str) -> str:
    return (
        "https://raw.githubusercontent.com/"
        f"{SOURCE_OWNER}/{SOURCE_REPO}/{branch}/{relative_path}"
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def reset_output_dirs() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    SEARCH_DIR.mkdir(parents=True, exist_ok=True)
    SETS_DIR.mkdir(parents=True, exist_ok=True)

    for directory in (CARDS_DIR, SEARCH_DIR, SETS_DIR):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)

    index_path = DOCS_DIR / "index.json"
    if index_path.exists():
        index_path.unlink()

    (DOCS_DIR / ".nojekyll").touch()


def simplify_card(card: dict[str, Any], set_record: dict[str, Any]) -> dict[str, Any]:
    images = card.get("images", {})
    return {
        "id": card["id"],
        "name": card.get("name"),
        "set": set_record.get("name"),
        "setId": set_record.get("id"),
        "number": card.get("number"),
        "rarity": card.get("rarity"),
        "types": card.get("types") or [],
        "hp": card.get("hp"),
        "artist": card.get("artist"),
        "imageSmall": images.get("small"),
        "imageLarge": images.get("large"),
    }


def simplify_set(set_record: dict[str, Any], card_count: int) -> dict[str, Any]:
    images = set_record.get("images", {})
    return {
        "id": set_record.get("id"),
        "name": set_record.get("name"),
        "series": set_record.get("series"),
        "printedTotal": set_record.get("printedTotal"),
        "total": set_record.get("total"),
        "cardCount": card_count,
        "releaseDate": set_record.get("releaseDate"),
        "updatedAt": set_record.get("updatedAt"),
        "symbolImage": images.get("symbol"),
        "logoImage": images.get("logo"),
    }


def card_sort_key(card: dict[str, Any]) -> tuple[str, str, str]:
    return (
        (card.get("name") or "").casefold(),
        card.get("setId") or "",
        card.get("number") or "",
    )


def split_natural(value: str | None) -> list[int | str]:
    if not value:
        return []
    pieces = re.split(r"(\d+)", value)
    return [int(piece) if piece.isdigit() else piece.casefold() for piece in pieces]


def set_card_sort_key(card: dict[str, Any]) -> tuple[list[int | str], str]:
    return (split_natural(card.get("number")), (card.get("name") or "").casefold())


def set_sort_key(set_record: dict[str, Any]) -> tuple[str, str]:
    return (
        set_record.get("releaseDate") or "",
        set_record.get("id") or "",
    )


def normalize_name_for_search(name: str | None) -> str:
    if not name:
        return ""

    normalized = name.casefold()
    normalized = re.sub(r"[^\w\s]|_", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def word_to_shard_key(word: str) -> str:
    if len(word) >= 2:
        return word[:2]
    return word.ljust(2, word[-1])


def shard_keys_for_card(card: dict[str, Any]) -> set[str]:
    normalized_name = normalize_name_for_search(card.get("name"))
    words = normalized_name.split()
    return {
        word_to_shard_key(word)
        for word in words
        if word
    }


def fetch_cards_for_set(branch: str, set_record: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    set_id = set_record["id"]
    url = raw_url(branch, f"cards/en/{set_id}.json")
    cards = fetch_json(url)
    return set_id, [simplify_card(card, set_record) for card in cards]


def generate() -> dict[str, int]:
    repo_metadata = fetch_repo_metadata()
    branch = repo_metadata["default_branch"]
    set_records = fetch_json(raw_url(branch, "sets/en.json"))

    reset_output_dirs()

    set_index: list[dict[str, Any]] = []
    search_shards: dict[str, list[dict[str, Any]]] = {}

    print(
        f"Fetching {len(set_records)} sets from "
        f"{SOURCE_OWNER}/{SOURCE_REPO}@{branch}..."
    )

    cards_by_set: dict[str, list[dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {
            executor.submit(fetch_cards_for_set, branch, set_record): set_record
            for set_record in set_records
        }
        for future in as_completed(future_map):
            set_record = future_map[future]
            set_id, cards = future.result()
            cards_by_set[set_id] = cards
            print(f"Loaded {set_id} ({len(cards)} cards)")

    for set_record in sorted(set_records, key=set_sort_key):
        set_id = set_record["id"]
        cards = cards_by_set[set_id]
        cards.sort(key=set_card_sort_key)

        set_summary = simplify_set(set_record, len(cards))
        set_index.append(set_summary)
        write_json(SETS_DIR / f"{set_id}.json", {**set_summary, "cards": cards})

        for card in cards:
            write_json(CARDS_DIR / f"{card['id']}.json", card)
            for shard_key in shard_keys_for_card(card):
                search_shards.setdefault(shard_key, []).append(card)

    for shard_key, cards in search_shards.items():
        cards.sort(key=card_sort_key)
        write_json(SEARCH_DIR / f"{shard_key}.json", cards)

    write_json(SETS_DIR / "index.json", set_index)
    write_json(
        DOCS_DIR / "meta.json",
        {
            "name": "Poketom API",
            "generatedFrom": f"{SOURCE_OWNER}/{SOURCE_REPO}",
            "defaultBranch": branch,
            "cardCount": sum(len(cards) for cards in cards_by_set.values()),
            "setCount": len(set_index),
            "searchShardCount": len(search_shards),
        },
    )

    return {
        "cards": sum(len(cards) for cards in cards_by_set.values()),
        "sets": len(set_index),
        "shards": len(search_shards),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a static Pokemon TCG JSON API for GitHub Pages."
    )
    return parser.parse_args()


def main() -> None:
    parse_args()
    counts = generate()
    print(
        f"Generated {counts['cards']} cards across {counts['sets']} sets and "
        f"{counts['shards']} search shards in "
        f"{DOCS_DIR}"
    )


if __name__ == "__main__":
    main()
