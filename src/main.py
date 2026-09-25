"""Fun fact for today - picks interesting facts about today's date from Wikipedia "On this day"."""

from __future__ import annotations

import asyncio
import random
import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from apify import Actor

API_URL = 'https://api.wikimedia.org/feed/v1/wikipedia/{lang}/onthisday/{type}/{mm}/{dd}'
USER_AGENT = 'FunFactForToday/1.0 (Apify Actor; https://apify.com)'
FACT_TYPES = ('selected', 'events', 'births', 'deaths', 'holidays')
LANG_RE = re.compile(r'^[a-z]{2,3}(-[a-z]+)?$')
# Wikipedia main-page hints such as "(pictured)" refer to images we don't show.
PICTURED_RE = re.compile(r'\s*\((?:pictured|shown|depicted|illustrated)(?: [a-z ]+)?\)', re.IGNORECASE)
MAX_RETRIES = 3


def resolve_date(date_str: str | None, timezone: str) -> date:
    """Return the requested date, or today's date in the given timezone."""
    if date_str:
        date_str = date_str.strip()
        for fmt in ('%Y-%m-%d', '%m-%d'):
            try:
                parsed = datetime.strptime(date_str if fmt == '%Y-%m-%d' else f'2024-{date_str}', '%Y-%m-%d')
            except ValueError:
                continue
            if fmt == '%Y-%m-%d':
                return parsed.date()
            # MM-DD: use the current year (02-29 falls back to the leap year 2024).
            try:
                return date(date.today().year, parsed.month, parsed.day)
            except ValueError:
                return parsed.date()
        raise ValueError(f'Invalid date "{date_str}". Use YYYY-MM-DD or MM-DD.')
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f'Unknown timezone "{timezone}".') from exc
    return datetime.now(tz).date()


def normalize_item(raw: dict[str, Any], fact_type: str, day: date, language: str) -> dict[str, Any] | None:
    """Turn one raw Wikipedia entry into a clean output item. Returns None for malformed entries."""
    text = raw.get('text')
    if not isinstance(text, str) or not text.strip():
        return None
    text = PICTURED_RE.sub('', ' '.join(text.split())).strip()

    year = raw.get('year')
    year = year if isinstance(year, int) else None

    pages = raw.get('pages') if isinstance(raw.get('pages'), list) else []
    page = next((p for p in pages if isinstance(p, dict)), {})
    titles = page.get('titles') if isinstance(page.get('titles'), dict) else {}
    urls = page.get('content_urls') if isinstance(page.get('content_urls'), dict) else {}
    desktop = urls.get('desktop') if isinstance(urls.get('desktop'), dict) else {}
    thumb = page.get('thumbnail') if isinstance(page.get('thumbnail'), dict) else {}

    wiki_url = desktop.get('page')
    thumb_url = thumb.get('source')
    extract = page.get('extract')

    date_label = f'{day.strftime("%B")} {day.day}'
    year_label = (f'{-year} BC' if year < 0 else str(year)) if year is not None else None
    if language != 'en':
        # Text is in the Wikipedia language, so keep the sentence language-neutral.
        fun_fact = f'{day.day}. {day.month}. {year_label}: {text}' if year_label else f'{day.day}. {day.month}.: {text}'
    elif fact_type == 'holidays':
        fun_fact = f'On {date_label}, people observe: {text}'
    elif year is not None:
        verb = {'births': 'was born', 'deaths': 'died'}.get(fact_type)
        fun_fact = f'On {date_label}, {year_label}, {text} {verb}.' if verb else f'On {date_label}, {year_label}: {text}'
    else:
        fun_fact = f'On {date_label}: {text}'

    return {
        'date': day.strftime('%m-%d'),
        'type': fact_type,
        'year': year,
        'yearsAgo': (date.today().year - year) if year is not None else None,
        'text': text,
        'funFact': fun_fact,
        'wikipediaTitle': titles.get('normalized') or page.get('title'),
        'wikipediaExtract': extract if isinstance(extract, str) else None,
        'wikipediaUrl': wiki_url if isinstance(wiki_url, str) and wiki_url.startswith('https://') else None,
        'thumbnailUrl': thumb_url if isinstance(thumb_url, str) and thumb_url.startswith('https://') else None,
        'language': language,
    }


async def fetch_on_this_day(client: httpx.AsyncClient, language: str, fact_type: str, day: date) -> dict[str, Any]:
    """Download the "On this day" feed with retries and exponential backoff."""
    url = API_URL.format(lang=language, type=fact_type, mm=f'{day.month:02d}', dd=f'{day.day:02d}')
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await client.get(url)
            if response.status_code == 404:
                raise ValueError(f'Wikipedia "On this day" feed is not available for language "{language}".')
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError('Unexpected response format from Wikipedia.')
            return data
        except (httpx.HTTPError, ValueError) as exc:
            if isinstance(exc, ValueError) or attempt == MAX_RETRIES:
                raise
            delay = 2**attempt
            Actor.log.warning(f'Request failed ({exc}), retrying in {delay}s (attempt {attempt}/{MAX_RETRIES})')
            await asyncio.sleep(delay)
    raise RuntimeError('unreachable')


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        language = str(actor_input.get('language') or 'en').strip().lower()
        fact_types = actor_input.get('factTypes') or ['selected']
        max_facts = int(actor_input.get('maxFacts') or 1)
        randomize = bool(actor_input.get('randomize', True))
        timezone = str(actor_input.get('timezone') or 'UTC')

        if not LANG_RE.match(language):
            await Actor.fail(status_message=f'Invalid language code "{language}".')
            return
        invalid = [t for t in fact_types if t not in FACT_TYPES]
        if invalid:
            await Actor.fail(status_message=f'Invalid fact types: {invalid}. Allowed: {list(FACT_TYPES)}')
            return
        if not 1 <= max_facts <= 500:
            await Actor.fail(status_message='maxFacts must be between 1 and 500.')
            return
        try:
            day = resolve_date(actor_input.get('date'), timezone)
        except ValueError as exc:
            await Actor.fail(status_message=str(exc))
            return

        Actor.log.info(f'Looking up fun facts for {day:%B %d} ({language}.wikipedia.org), types: {fact_types}')

        async with httpx.AsyncClient(
            headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'},
            timeout=30,
            follow_redirects=True,
        ) as client:
            # "all" returns every section in one request.
            api_type = 'all' if len(fact_types) > 1 else fact_types[0]
            try:
                data = await fetch_on_this_day(client, language, api_type, day)
            except Exception as exc:
                await Actor.fail(status_message=f'Failed to fetch facts: {exc}')
                return

        per_type: list[list[dict[str, Any]]] = []
        for fact_type in fact_types:
            section = data.get(fact_type)
            if not isinstance(section, list):
                continue
            parsed = [i for raw in section if isinstance(raw, dict) and (i := normalize_item(raw, fact_type, day, language))]
            if parsed:
                per_type.append(parsed)

        if randomize:
            items = [i for group in per_type for i in group]
        else:
            # Round-robin across types so each requested type shows up, keeping Wikipedia's order within a type.
            items = [g[idx] for idx in range(max((len(g) for g in per_type), default=0)) for g in per_type if idx < len(g)]

        if not items:
            await Actor.fail(status_message=f'No facts found for {day:%m-%d} in language "{language}".')
            return

        if randomize:
            random.shuffle(items)
        items = items[:max_facts]

        await Actor.push_data(items)
        await Actor.set_value('FUN_FACT', items[0])

        Actor.log.info(f'Fun fact for today: {items[0]["funFact"]}')
        await Actor.set_status_message(f'Saved {len(items)} fun fact(s) for {day:%B %d}.')
