"""Extract Mitacs project-list cards into a clean CSV/JSON dataset."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


API_URL = "https://globalink.mitacs.ca/api/sasprojectlistpaging"
PAGE_SIZE = 10  # The website itself shows ten project cards per page.
FIELDS = [
    "project_id",
    "title",
    "introduction",
    "faculty_supervisor",
    "faculty_province",
    "faculty_university",
    "faculty_campus",
    "project_location",
    "language",
    "preferred_start_date",
]


def normalized_text(value: Any) -> str:
    """Make scraped text safe as one physical CSV line per project."""
    text = re.sub(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]+", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def normalized_date(value: Any) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return str(value)


def project_card(raw: dict[str, Any]) -> dict[str, str]:
    """Convert one API row to exactly the fields visible in the screenshot."""
    professor = raw.get("Professor") or {}
    first = raw.get("Professor.FirstName") or professor.get("FirstName") or ""
    last = raw.get("Professor.LastName") or professor.get("LastName") or ""
    city = normalized_text(raw.get("City"))
    province = normalized_text(raw.get("Province"))
    return {
        "project_id": normalized_text(raw.get("ProjectID")),
        "title": normalized_text(raw.get("ProjectTitle")),
        "introduction": normalized_text(raw.get("projectDescription") or raw.get("ProjectDescription")),
        "faculty_supervisor": " ".join(x for x in (normalized_text(first), normalized_text(last)) if x),
        "faculty_province": normalized_text(raw.get("Professor.FacultyProvince") or professor.get("FacultyProvince")),
        "faculty_university": normalized_text(raw.get("Professor.UniversityName") or professor.get("UniversityName")),
        "faculty_campus": normalized_text(raw.get("Professor.CampusName") or professor.get("CampusName")),
        "project_location": ", ".join(x for x in (city, province) if x),
        "language": normalized_text(raw.get("LanguageUsed")),
        "preferred_start_date": normalized_date(raw.get("StartDate")),
    }


def fetch_page(session: requests.Session, filters: dict[str, Any], page: int) -> dict[str, Any]:
    payload = {**filters, "offset": (page - 1) * PAGE_SIZE, "limit": PAGE_SIZE}
    last_error: Exception | None = None
    for attempt in range(6):
        try:
            response = session.post(API_URL, json=payload, timeout=60)
            if response.status_code == 429:
                time.sleep(min(30, 3 * (attempt + 1)))
                continue
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
                raise ValueError("unexpected response structure")
            return data
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            time.sleep(min(16, 2**attempt))
    raise RuntimeError(f"page {page} failed after retries: {last_error}")


def filters_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "HostProvinceName": args.province or None,
        "HostUniversityID": args.university_id,
        "HostCampusID": args.campus_id,
        "LanguageUsed": args.language or None,
        "keyword": args.keyword or None,
        "FirstName": args.faculty_first_name or None,
        "LastName": args.faculty_last_name or None,
        "AcademicDiscipline": args.academic_discipline or None,
        "PreferredBackgroundCollection": args.preferred_background or None,
    }


def crawl(args: argparse.Namespace) -> tuple[list[dict[str, str]], int, int]:
    session = requests.Session()
    session.headers.update({
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://globalink.mitacs.ca",
        "Referer": "https://globalink.mitacs.ca/#/student/application/projects",
        "User-Agent": "Mozilla/5.0 MitacsProjectExtractor/2.0",
    })
    filters = filters_from_args(args)
    cards: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    total = 0
    total_pages = 1
    page = args.start_page

    while page <= total_pages:
        result = fetch_page(session, filters, page)
        total = int(result.get("count", len(result["rows"])))
        total_pages = max(1, math.ceil(total / PAGE_SIZE))
        for raw in result["rows"]:
            card = project_card(raw)
            if not card["project_id"]:
                raise RuntimeError(f"page {page} contains a project without project_id")
            if card["project_id"] not in seen_ids:
                seen_ids.add(card["project_id"])
                cards.append(card)
        print(f"page {page}/{total_pages}: collected {len(cards)} of {total}", flush=True)
        if args.max_pages and page - args.start_page + 1 >= args.max_pages:
            break
        page += 1
        time.sleep(args.delay)
    return cards, total, total_pages


def write_results(cards: list[dict[str, str]], output_dir: Path, total: int, pages: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "mitacs_projects.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(cards)
    (output_dir / "mitacs_projects.json").write_text(
        json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "crawl_metadata.json").write_text(
        json.dumps({
            "matching_projects_on_site": total,
            "matching_pages_on_site": pages,
            "projects_exported": len(cards),
            "page_size": PAGE_SIZE,
            "fields": FIELDS,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--keyword")
    parser.add_argument("--language")
    parser.add_argument("--province")
    parser.add_argument("--university-id", type=int)
    parser.add_argument("--campus-id", type=int)
    parser.add_argument("--faculty-first-name")
    parser.add_argument("--faculty-last-name")
    parser.add_argument("--academic-discipline")
    parser.add_argument("--preferred-background")
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--max-pages", type=int, help="use 1 for a safe ten-project preview")
    parser.add_argument("--delay", type=float, default=0.2)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.start_page < 1 or (args.max_pages is not None and args.max_pages < 1):
        raise SystemExit("--start-page and --max-pages must be positive")
    cards, total, pages = crawl(args)
    write_results(cards, args.output_dir, total, pages)
    print(f"done: exported {len(cards)} projects to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
