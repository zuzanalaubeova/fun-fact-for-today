import json
import os
from datetime import date
from pathlib import Path

import httpx
import pytest

from src import main as m

FIXTURE = json.loads((Path(__file__).parent / 'fixture_0925.json').read_text())


def test_resolve_date():
    assert m.resolve_date('2025-09-25', 'UTC') == date(2025, 9, 25)
    assert m.resolve_date('02-29', 'UTC').month == 2
    assert m.resolve_date(None, 'Europe/Prague') is not None
    with pytest.raises(ValueError):
        m.resolve_date('25.9.', 'UTC')
    with pytest.raises(ValueError):
        m.resolve_date(None, 'Mars/Olympus')


def test_normalize():
    d = date(2026, 9, 25)
    item = m.normalize_item(FIXTURE['selected'][0], 'selected', d, 'en')
    assert item['yearsAgo'] == date.today().year - 1789
    assert item['funFact'].startswith('On September 25, 1789:')
    assert item['wikipediaTitle'] == 'United States Bill of Rights'
    assert m.normalize_item(FIXTURE['births'][0], 'births', d, 'en')['funFact'].endswith('was born.')
    assert 'observe' in m.normalize_item(FIXTURE['holidays'][0], 'holidays', d, 'en')['funFact']
    assert '1 BC' in m.normalize_item(FIXTURE['events'][0], 'events', d, 'en')['funFact']
    assert m.normalize_item({'text': '  '}, 'selected', d, 'en') is None
    # past full date must not produce negative yearsAgo for recent events
    assert m.normalize_item({'text': 'X', 'year': 2024}, 'deaths', date(1999, 12, 31), 'en')['yearsAgo'] >= 0


def test_pictured_and_language():
    d = date(2026, 9, 25)
    item = m.normalize_item({'text': "Sandra Day O'Connor (pictured) became the first female justice.", 'year': 1981}, 'selected', d, 'en')
    assert '(pictured)' not in item['text'] and "O'Connor became" in item['text']
    de = m.normalize_item({'text': 'Christian Steinmüller, deutscher Orgelbauer', 'year': 1792}, 'births', d, 'de')
    assert de['funFact'] == '25. 9. 1792: Christian Steinmüller, deutscher Orgelbauer'


async def _run(tmp_path, monkeypatch, actor_input, handler):
    storage = tmp_path / 'storage'
    kvs = storage / 'key_value_stores' / 'default'
    kvs.mkdir(parents=True)
    (kvs / 'INPUT.json').write_text(json.dumps(actor_input))
    monkeypatch.setenv('CRAWLEE_STORAGE_DIR', str(storage))
    monkeypatch.setenv('CRAWLEE_PURGE_ON_START', 'false')
    real_client = httpx.AsyncClient
    monkeypatch.setattr(m.httpx, 'AsyncClient', lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    exit_code = 0
    try:
        await m.main()
    except SystemExit as e:
        exit_code = e.code
    ds = storage / 'datasets' / 'default'
    items = [json.loads(p.read_text()) for p in sorted(ds.glob('0*.json'))] if ds.exists() else []
    return exit_code, items, kvs


@pytest.mark.asyncio
async def test_full_run(tmp_path, monkeypatch):
    seen = []

    def handler(req):
        seen.append(str(req.url))
        assert req.headers['user-agent'].startswith('FunFactForToday')
        return httpx.Response(200, json=FIXTURE)

    code, items, kvs = await _run(tmp_path, monkeypatch,
                                  {'factTypes': ['selected', 'births', 'holidays'], 'maxFacts': 10, 'randomize': False, 'date': '09-25'}, handler)
    assert code in (0, None)
    assert seen[0].endswith('/onthisday/all/09/25')
    assert len(items) == 4
    # round-robin: first items cover every requested type
    assert [i['type'] for i in items[:3]] == ['selected', 'births', 'holidays']
    assert json.loads((kvs / 'FUN_FACT').read_text())['year'] == 1789


@pytest.mark.asyncio
async def test_bad_language(tmp_path, monkeypatch):
    code, items, _ = await _run(tmp_path, monkeypatch, {'language': 'xx'}, lambda r: httpx.Response(404))
    assert code == 1 and items == []
