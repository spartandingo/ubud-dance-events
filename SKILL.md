---
name: embodied-events
description: Fetch and deduplicate embodied practice events (dance, tantra, rope/shibari) from WhatsApp, Telegram, and Instagram across multiple regions. Use when asking about upcoming ecstatic dance, contact improv, tantra, shibari, movement classes, or workshops.
---

# Embodied Events

Pull upcoming embodied practice events from WhatsApp, Telegram, and Instagram. Supports multiple regions and event categories.

## Quick Start

```bash
cd skills/embodied-events
source .venv/bin/activate

# Check source status
python3 scripts/fetch-events-v2.py --status

# Fetch all events (last 7 days, all regions, all categories)
python3 scripts/fetch-events-v2.py

# Filter by region
python3 scripts/fetch-events-v2.py --region ubud
python3 scripts/fetch-events-v2.py --region bali
python3 scripts/fetch-events-v2.py --region northern-rivers

# Filter by category
python3 scripts/fetch-events-v2.py --category dance
python3 scripts/fetch-events-v2.py --category tantra
python3 scripts/fetch-events-v2.py --category rope

# Combine filters
python3 scripts/fetch-events-v2.py --region bali --category dance

# JSON output for parsing
python3 scripts/fetch-events-v2.py --json

# Custom lookback
python3 scripts/fetch-events-v2.py --days 14
```

## Regions

| Region | Timezone | Description |
|--------|----------|-------------|
| `ubud` | Asia/Makassar (WITA) | Ubud, Bali |
| `bali` | Asia/Makassar (WITA) | Wider Bali area |
| `northern-rivers` | Australia/Sydney | Northern Rivers, NSW |

## Categories

| Category | Description |
|----------|-------------|
| `dance` | Ecstatic dance, contact improv, 5Rhythms, movement, jams |
| `tantra` | Tantra, sacred sexuality, pujas, temple events |
| `rope` | Shibari, rope bondage, In.Ropes events |

## Sources

### WhatsApp (via wacli)

Groups are configured in `config.json` with region and category tags. Each group can belong to multiple categories.

Requires `wacli` to be authenticated (`wacli auth`).

### Telegram (via Telethon)

Groups and forums configured with region/category tags.

**Setup:**
1. Get API credentials from https://my.telegram.org
2. Copy `.env.example` to `.env` and add credentials
3. Authenticate: `python3 scripts/telegram_auth.py`

### Instagram (via instaloader + vision)

Fetches weekly schedule images from venue profiles.

```bash
python3 scripts/fetch-instagram.py
python3 scripts/fetch-instagram.py --list
python3 scripts/fetch-instagram.py --clear
```

## Config Structure

```json
{
  "regions": {
    "region-id": { "name": "Display Name", "timezone": "TZ" }
  },
  "categories": {
    "category-id": { "name": "Display Name", "search_terms": [...] }
  },
  "whatsapp": {
    "groups": {
      "JID": {
        "name": "Group Name",
        "region": "region-id",
        "categories": ["cat1", "cat2"]
      }
    }
  }
}
```

Groups can have multiple categories — events are fetched once, then tagged based on content matching category search terms.

## Architecture

```
sources/
├── base.py        # RawEvent dataclass + EventSource ABC
├── parser.py      # Text parsing (dates, venues, links)
├── whatsapp.py    # WhatsApp via wacli
├── telegram.py    # Telegram via Telethon
├── instagram.py   # Instagram via instaloader + vision
└── aggregator.py  # Multi-source fetch + deduplication
```

## Common Venues (Bali)

- **Paradiso Ubud** — ecstatic, contact improv, workshops
- **Moksa Ubud** — Contact Dojo jams
- **Rasa Ubud Yoga Studio** — workshops, intensives
- **The Yoga Barn** — occasional events
- **Morabito** — beachfront events, festivals
- **AmrtaSiddhi** — CI jams

## Common Venues (Northern Rivers)

- **Mullumbimby** — contact improv community

## Event Types

**Dance:**
- Ecstatic dance (RESONANZ, Dance Temple)
- Contact improvisation (Dissolve & Play, Kinetic, jams)
- Movement workshops (Gaga, contemporary, somatic)
- 5Rhythms

**Tantra:**
- Tantra temples
- Sacred sexuality workshops
- Pujas
- Kundalini events

**Rope:**
- Shibari jams
- Rope workshops
- In.Ropes events
