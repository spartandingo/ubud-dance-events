#!/usr/bin/env python3
"""
Generate the Embodied Events static HTML page from event data.

Usage:
    python3 generate-site.py                    # Generate from events-this-week.md
    python3 generate-site.py --fetch            # Fetch fresh events first
    python3 generate-site.py --output docs/     # Custom output directory
"""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

script_dir = Path(__file__).parent
skill_dir = script_dir.parent


def load_venues() -> dict:
    """Load venue configuration."""
    venues_path = skill_dir / "venues.json"
    if venues_path.exists():
        with open(venues_path) as f:
            return json.load(f).get("venues", {})
    return {}


def parse_events_markdown(md_path: Path) -> dict:
    """Parse events-this-week.md into structured data."""
    if not md_path.exists():
        return {"days": [], "generated": None}
    
    content = md_path.read_text()
    
    # Extract generation date
    gen_match = re.search(r"Generated: (.+)", content)
    generated = gen_match.group(1) if gen_match else None
    
    # Parse days and events
    days = []
    current_day = None
    current_date = None
    
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Day header: ## Monday, January 26
        day_match = re.match(r"^## (\w+), (\w+ \d+)", line)
        if day_match:
            if current_day:
                days.append(current_day)
            current_day = {
                "day_name": day_match.group(1),
                "date": day_match.group(2),
                "events": []
            }
            i += 1
            continue
        
        # Event header: ### ~ Event Name or ### ? Event Name or ### ✓ Event Name
        event_match = re.match(r"^### ([~?✓]) (.+)", line)
        if event_match and current_day is not None:
            status = event_match.group(1)
            name = event_match.group(2)
            
            event = {
                "name": name,
                "status": status,
                "time": None,
                "venue": None,
                "price": None,
                "description": None,
                "ticket_link": None,
                "sources": []
            }
            
            # Parse following lines for event details
            i += 1
            while i < len(lines):
                detail = lines[i].strip()
                if not detail or detail.startswith("##") or detail.startswith("---"):
                    break
                
                # Time: 🕐 6pm–9pm
                time_match = re.match(r"^🕐\s*(.+)", detail)
                if time_match:
                    event["time"] = time_match.group(1)
                    i += 1
                    continue
                
                # Venue: 📍 Paradiso
                venue_match = re.match(r"^📍\s*(.+)", detail)
                if venue_match:
                    event["venue"] = venue_match.group(1)
                    i += 1
                    continue
                
                # Price: 💰 200k
                price_match = re.match(r"^💰\s*(.+)", detail)
                if price_match:
                    event["price"] = price_match.group(1)
                    i += 1
                    continue
                
                # Description/notes: *text*
                desc_match = re.match(r"^\*([^*]+)\*$", detail)
                if desc_match:
                    text = desc_match.group(1)
                    if text.startswith("via "):
                        event["sources"] = [s.strip() for s in text[4:].split(",")]
                    elif event["description"]:
                        event["description"] += " " + text
                    else:
                        event["description"] = text
                    i += 1
                    continue
                
                # Ticket link
                link_match = re.search(r"https?://[^\s]+", detail)
                if link_match:
                    event["ticket_link"] = link_match.group(0)
                
                i += 1
            
            current_day["events"].append(event)
            continue
        
        i += 1
    
    if current_day:
        days.append(current_day)
    
    return {"days": days, "generated": generated}


def generate_html(events_data: dict, venues: dict, is_full: bool = False) -> str:
    """Generate the full HTML page."""
    
    days = events_data.get("days", [])
    generated = events_data.get("generated", datetime.now().strftime("%Y-%m-%d %H:%M"))
    
    # Get today's day name
    today = datetime.now().strftime("%A")
    
    # Title and notice for full version
    title = "Embodied Events (Full)" if is_full else "Embodied Events"
    full_notice = ""
    if is_full:
        full_notice = '''
            <div class="full-notice">
                🔒 Full calendar — includes invite-only events. Please don't share publicly.
            </div>
'''
    
    # Build events HTML
    events_html = ""
    for day in days:
        is_today = day["day_name"] == today
        today_class = " today" if is_today else ""
        
        events_html += f'''
            <h3 class="day-header{today_class}" data-region="bali">{day["day_name"]} <span class="day-date">{day["date"]}</span></h3>
            <div class="events-list" data-region="bali">
'''
        
        for event in day["events"]:
            venue = event.get("venue", "")
            venue_data = venues.get(venue, {})
            maps_url = venue_data.get("maps_url", "")
            region = venue_data.get("region", "bali")
            
            time_display = event.get("time", "TBA") or "TBA"
            price_display = event.get("price", "—") or "—"
            
            # Build venue link
            if maps_url:
                venue_html = f'<a href="{maps_url}" target="_blank" class="event-venue">{venue} ↗</a>'
            else:
                venue_html = f'<span class="event-venue">{venue}</span>' if venue else ''
            
            # Build ticket link
            ticket_html = ""
            if event.get("ticket_link"):
                ticket_html = f'<a href="{event["ticket_link"]}" target="_blank" class="event-tickets">Tickets ↗</a>'
            
            # Build description
            desc_html = ""
            if event.get("description"):
                desc_html = f'<div class="event-desc">{event["description"]}</div>'
            
            # Status indicator
            status_map = {"~": "likely", "?": "tentative", "✓": "confirmed"}
            status_class = status_map.get(event.get("status", "~"), "likely")
            
            events_html += f'''
                <details class="event-card" data-status="{status_class}" data-region="{region}">
                    <summary class="event-summary">
                        <span class="event-time">{time_display}</span>
                        <div class="event-info">
                            <div class="event-name">{event["name"]}</div>
                            <div class="event-meta">{venue_html}{ticket_html}</div>
                        </div>
                        <span class="event-price">{price_display}</span>
                    </summary>
                    <div class="event-details">
                        {desc_html}
                        <div class="event-sources">via {", ".join(event.get("sources", []))}</div>
                    </div>
                </details>
'''
        
        events_html += "            </div>\n"
    
    # Full HTML template
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta name="description" content="Dance, tantra, rope, and movement events in Bali and beyond.">
    <meta name="theme-color" content="#0a0a0f">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --void: #0a0a0f;
            --deep: #12121a;
            --surface: #1a1a24;
            --edge: #2a2a38;
            --whisper: #4a4a5a;
            --smoke: #8a8a9a;
            --bone: #e8e4dc;
            --cream: #f5f2ea;
            --ember: #ff6b35;
            --ember-glow: rgba(255, 107, 53, 0.4);
            --violet: #9d4edd;
            --violet-glow: rgba(157, 78, 221, 0.3);
            --rose: #e84a5f;
            --rose-glow: rgba(232, 74, 95, 0.3);
            --serif: 'Cormorant Garamond', Georgia, serif;
            --mono: 'Space Mono', monospace;
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html {{ scroll-behavior: smooth; }}
        
        body {{
            font-family: var(--serif);
            background: var(--void);
            color: var(--cream);
            min-height: 100vh;
            overflow-x: hidden;
        }}
        
        .atmosphere {{
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: 0;
        }}
        
        .atmosphere::before {{
            content: '';
            position: absolute;
            top: -50%; left: -50%;
            width: 200%; height: 200%;
            background: 
                radial-gradient(ellipse 80% 50% at 20% 20%, var(--violet-glow), transparent 50%),
                radial-gradient(ellipse 60% 40% at 80% 70%, var(--ember-glow), transparent 50%),
                radial-gradient(ellipse 50% 50% at 50% 100%, var(--rose-glow), transparent 40%);
            animation: drift 20s ease-in-out infinite alternate;
        }}
        
        @keyframes drift {{
            0% {{ transform: translate(0, 0) rotate(0deg); }}
            100% {{ transform: translate(-5%, 3%) rotate(2deg); }}
        }}
        
        .grain {{
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: 1000;
            opacity: 0.03;
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
        }}
        
        .container {{
            position: relative;
            z-index: 1;
            max-width: 800px;
            margin: 0 auto;
            padding: 3rem 1.5rem;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 3rem;
        }}
        
        .sigil {{
            font-size: 3rem;
            margin-bottom: 1rem;
            display: flex;
            justify-content: center;
            gap: 0.5rem;
            filter: drop-shadow(0 0 30px var(--ember-glow));
        }}
        
        .sigil span {{
            display: inline-block;
            animation: float 3s ease-in-out infinite;
        }}
        .sigil span:nth-child(1) {{ animation-delay: 0s; }}
        .sigil span:nth-child(2) {{ animation-delay: 0.3s; }}
        .sigil span:nth-child(3) {{ animation-delay: 0.6s; }}
        
        @keyframes float {{
            0%, 100% {{ transform: translateY(0); }}
            50% {{ transform: translateY(-8px); }}
        }}
        
        h1 {{
            font-family: var(--serif);
            font-size: clamp(2.5rem, 8vw, 4rem);
            font-weight: 400;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            line-height: 1;
            margin-bottom: 0.75rem;
        }}
        
        .tagline {{
            font-family: var(--mono);
            font-size: 0.65rem;
            letter-spacing: 0.3em;
            text-transform: uppercase;
            color: var(--smoke);
        }}
        
        .full-notice {{
            background: linear-gradient(135deg, var(--violet-glow), var(--rose-glow));
            border: 1px solid var(--violet);
            padding: 0.75rem 1rem;
            margin-bottom: 1.5rem;
            font-family: var(--mono);
            font-size: 0.7rem;
            text-align: center;
            color: var(--cream);
        }}
        
        /* Tabs */
        .tabs {{
            display: flex;
            gap: 1px;
            background: var(--edge);
            margin-bottom: 2rem;
        }}
        
        .tab {{
            flex: 1;
            padding: 0.875rem 1rem;
            background: var(--deep);
            border: none;
            font-family: var(--mono);
            font-size: 0.65rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--smoke);
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        
        .tab:hover {{
            color: var(--cream);
            background: var(--surface);
        }}
        
        .tab.active {{
            color: var(--cream);
            background: var(--surface);
            box-shadow: inset 0 -2px 0 var(--ember);
        }}
        
        section {{ margin-bottom: 3rem; }}
        
        .section-label {{
            font-family: var(--mono);
            font-size: 0.6rem;
            letter-spacing: 0.4em;
            text-transform: uppercase;
            color: var(--whisper);
            margin-bottom: 1.25rem;
            display: flex;
            align-items: center;
            gap: 1rem;
        }}
        
        .section-label::after {{
            content: '';
            flex: 1;
            height: 1px;
            background: linear-gradient(90deg, var(--edge), transparent);
        }}
        
        .day-header {{
            font-family: var(--serif);
            font-size: 1.35rem;
            font-weight: 500;
            margin: 2rem 0 0.75rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--edge);
        }}
        
        .day-header:first-of-type {{ margin-top: 0; }}
        
        .day-date {{
            font-family: var(--mono);
            font-size: 0.6rem;
            color: var(--smoke);
            margin-left: 0.5rem;
        }}
        
        .today {{ color: var(--ember); }}
        
        .today::after {{
            content: 'TODAY';
            font-family: var(--mono);
            font-size: 0.5rem;
            letter-spacing: 0.2em;
            background: var(--ember);
            color: var(--void);
            padding: 0.15rem 0.4rem;
            margin-left: 0.75rem;
            vertical-align: middle;
        }}
        
        .events-list {{
            display: flex;
            flex-direction: column;
            gap: 1px;
            background: var(--edge);
        }}
        
        .event-card {{
            background: var(--deep);
            transition: background 0.3s ease;
        }}
        
        .event-card[open] {{
            background: var(--surface);
        }}
        
        .event-summary {{
            padding: 1rem 1.25rem;
            display: grid;
            grid-template-columns: 4.5rem 1fr auto;
            gap: 1rem;
            align-items: center;
            cursor: pointer;
            list-style: none;
        }}
        
        .event-summary::-webkit-details-marker {{ display: none; }}
        
        .event-summary:hover {{
            background: var(--surface);
        }}
        
        .event-time {{
            font-family: var(--mono);
            font-size: 0.75rem;
            font-weight: 700;
            color: var(--ember);
        }}
        
        .event-info {{ min-width: 0; }}
        
        .event-name {{
            font-family: var(--serif);
            font-size: 1.1rem;
            font-weight: 500;
            margin-bottom: 0.2rem;
        }}
        
        .event-meta {{
            font-family: var(--mono);
            font-size: 0.65rem;
            color: var(--bone);
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
        }}
        
        .event-venue {{
            color: var(--bone);
            text-decoration: none;
        }}
        
        .event-venue:hover {{
            color: var(--ember);
        }}
        
        .event-tickets {{
            color: var(--ember);
            text-decoration: none;
        }}
        
        .event-tickets:hover {{
            text-decoration: underline;
        }}
        
        .event-price {{
            font-family: var(--mono);
            font-size: 0.7rem;
            font-weight: 700;
            color: var(--bone);
        }}
        
        .event-details {{
            padding: 0 1.25rem 1rem 5.75rem;
            font-family: var(--mono);
            font-size: 0.75rem;
            color: var(--cream);
            line-height: 1.6;
        }}
        
        .event-desc {{
            margin-bottom: 0.5rem;
            color: var(--cream);
        }}
        
        .event-sources {{
            color: var(--smoke);
            font-size: 0.6rem;
        }}
        
        /* Subscribe */
        .subscribe-card {{
            background: var(--deep);
            border: 1px solid var(--edge);
            padding: 2rem;
            position: relative;
        }}
        
        .subscribe-card::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--ember), transparent);
        }}
        
        .subscribe-title {{
            font-family: var(--serif);
            font-size: 1.35rem;
            margin-bottom: 0.5rem;
        }}
        
        .subscribe-desc {{
            font-family: var(--mono);
            font-size: 0.65rem;
            color: var(--smoke);
            margin-bottom: 1.25rem;
        }}
        
        .url-display {{
            background: var(--void);
            border: 1px solid var(--edge);
            padding: 0.875rem;
            font-family: var(--mono);
            font-size: 0.65rem;
            color: var(--ember);
            word-break: break-all;
            cursor: pointer;
            margin-bottom: 1rem;
        }}
        
        .url-display:hover {{ border-color: var(--ember); }}
        
        .actions {{ display: flex; gap: 0.75rem; flex-wrap: wrap; }}
        
        .btn {{
            font-family: var(--mono);
            font-size: 0.6rem;
            letter-spacing: 0.15em;
            text-transform: uppercase;
            padding: 0.75rem 1.25rem;
            border: 1px solid var(--edge);
            background: transparent;
            color: var(--cream);
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
        }}
        
        .btn:hover {{
            background: var(--cream);
            color: var(--void);
            border-color: var(--cream);
        }}
        
        .btn-primary {{
            background: var(--ember);
            border-color: var(--ember);
            color: var(--void);
        }}
        
        .copied {{ background: #22c55e !important; border-color: #22c55e !important; }}
        
        footer {{
            text-align: center;
            padding-top: 2rem;
            border-top: 1px solid var(--edge);
            font-family: var(--mono);
            font-size: 0.55rem;
            color: var(--whisper);
        }}
        
        footer a {{ color: var(--smoke); text-decoration: none; }}
        footer a:hover {{ color: var(--ember); }}
        
        .hidden {{ display: none !important; }}
        
        @media (max-width: 640px) {{
            .container {{ padding: 2rem 1rem; }}
            .tabs {{ flex-wrap: wrap; }}
            .tab {{ flex: 1 1 45%; }}
            .event-summary {{ grid-template-columns: 1fr; gap: 0.5rem; }}
            .event-time {{ order: 1; }}
            .event-info {{ order: 0; }}
            .event-price {{ order: 2; }}
            .event-details {{ padding-left: 1.25rem; }}
            .subscribe-card {{ padding: 1.5rem; }}
            .actions {{ flex-direction: column; }}
        }}
    </style>
</head>
<body>
    <div class="atmosphere"></div>
    <div class="grain"></div>
    
    <div class="container">
        <header>
            <div class="sigil">
                <span>💃</span>
                <span>🕯️</span>
                <span>🪢</span>
            </div>
            <h1>Embodied</h1>
            <p class="tagline">Movement · Ritual · Connection</p>
        </header>
        {full_notice}
        <div class="tabs">
            <button class="tab active" data-filter="all">All</button>
            <button class="tab" data-filter="ubud">Ubud</button>
            <button class="tab" data-filter="bali">Bali</button>
            <button class="tab" data-filter="northern-rivers">NSW</button>
        </div>
        
        <section id="events">
            <div class="section-label">This Week</div>
            {events_html}
        </section>
        
        <section>
            <div class="section-label">Subscribe</div>
            <div class="subscribe-card">
                <h2 class="subscribe-title">Calendar Feed</h2>
                <p class="subscribe-desc">Add to your calendar for automatic updates</p>
                <div class="url-display" id="url" onclick="copyUrl()">
                    webcal://spartandingo.github.io/ubud-dance-events/ubud-dance-events.ics
                </div>
                <div class="actions">
                    <button class="btn btn-primary" id="copyBtn" onclick="copyUrl()">◎ Copy URL</button>
                    <a class="btn" href="ubud-dance-events.ics" download>↓ Download</a>
                </div>
            </div>
        </section>
        
        <footer>
            Updated {generated} · <a href="https://github.com/clawdbot/clawdbot">Clawdbot</a>
        </footer>
    </div>
    
    <script>
        // Tab filtering
        document.querySelectorAll('.tab').forEach(tab => {{
            tab.addEventListener('click', () => {{
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                
                const filter = tab.dataset.filter;
                
                // First, filter individual event cards
                document.querySelectorAll('.event-card').forEach(card => {{
                    if (filter === 'all') {{
                        card.classList.remove('hidden');
                    }} else if (filter === 'bali') {{
                        // Bali tab shows both bali and ubud
                        card.classList.toggle('hidden', 
                            card.dataset.region !== 'bali' && card.dataset.region !== 'ubud');
                    }} else {{
                        card.classList.toggle('hidden', card.dataset.region !== filter);
                    }}
                }});
                
                // Then, show/hide day headers and event lists based on whether they have visible events
                document.querySelectorAll('.events-list').forEach(list => {{
                    const hasVisibleEvents = list.querySelector('.event-card:not(.hidden)');
                    list.classList.toggle('hidden', !hasVisibleEvents);
                }});
                
                document.querySelectorAll('.day-header').forEach(header => {{
                    const nextList = header.nextElementSibling;
                    if (nextList && nextList.classList.contains('events-list')) {{
                        header.classList.toggle('hidden', nextList.classList.contains('hidden'));
                    }}
                }});
            }});
        }});
        
        function copyUrl() {{
            const url = document.getElementById('url').textContent.trim();
            navigator.clipboard.writeText(url).then(() => {{
                const btn = document.getElementById('copyBtn');
                btn.textContent = '✓ Copied';
                btn.classList.add('copied');
                setTimeout(() => {{
                    btn.textContent = '◎ Copy URL';
                    btn.classList.remove('copied');
                }}, 2000);
            }});
        }}
    </script>
</body>
</html>'''
    
    return html


def main():
    parser = argparse.ArgumentParser(description="Generate Embodied Events static site")
    parser.add_argument("--output", "-o", default="docs", help="Output directory")
    parser.add_argument("--fetch", action="store_true", help="Fetch fresh events first")
    parser.add_argument("--visibility", choices=["public", "all"], default="all", help="Which events to include")
    args = parser.parse_args()
    
    output_dir = skill_dir / args.output
    output_dir.mkdir(exist_ok=True)
    
    # Load venues and config
    venues = load_venues()
    config = load_config()
    
    # Parse events
    events_md = skill_dir / "events-this-week.md"
    events_data = parse_events_markdown(events_md)
    
    total_events = sum(len(d['events']) for d in events_data['days'])
    print(f"Parsed {total_events} events across {len(events_data['days'])} days")
    
    # Generate PUBLIC version (index.html)
    public_events = filter_events_by_visibility(events_data, "public", config)
    public_count = sum(len(d['events']) for d in public_events['days'])
    public_html = generate_html(public_events, venues, is_full=False)
    (output_dir / "index.html").write_text(public_html)
    print(f"Generated index.html ({public_count} public events)")
    
    # Generate FULL version (full/index.html) - behind Cloudflare Access
    full_dir = output_dir / "full"
    full_dir.mkdir(exist_ok=True)
    full_html = generate_html(events_data, venues, is_full=True)
    (full_dir / "index.html").write_text(full_html)
    print(f"Generated full/index.html ({total_events} total events)")


def load_config() -> dict:
    """Load config.json."""
    config_path = skill_dir / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}


def get_source_visibility(source_name: str, config: dict) -> str:
    """Determine visibility for an event based on its source."""
    # Check all source types for matching name
    for source_type in ["whatsapp", "telegram", "websites", "instagram"]:
        source_config = config.get(source_type, {})
        
        # Check groups
        for group_id, group_cfg in source_config.get("groups", {}).items():
            if group_cfg.get("name") == source_name:
                return group_cfg.get("visibility", "public")
        
        # Check sites
        for site_id, site_cfg in source_config.get("sites", {}).items():
            if site_cfg.get("name") == source_name:
                return site_cfg.get("visibility", "public")
        
        # Check profiles
        for profile_id, profile_cfg in source_config.get("profiles", {}).items():
            if profile_cfg.get("name") == source_name:
                return profile_cfg.get("visibility", "public")
        
        # Check forums
        for forum_id, forum_cfg in source_config.get("forums", {}).items():
            if forum_cfg.get("name") == source_name:
                return forum_cfg.get("visibility", "public")
    
    # Default to public for unknown sources
    return "public"


def filter_events_by_visibility(events_data: dict, visibility: str, config: dict) -> dict:
    """Filter events to only include those matching visibility."""
    if visibility == "all":
        return events_data
    
    filtered_days = []
    for day in events_data.get("days", []):
        filtered_events = []
        for event in day.get("events", []):
            # Check if event is marked private with 🔒
            if "🔒" in event.get("name", ""):
                if visibility == "private":
                    event["name"] = event["name"].replace("🔒", "").strip()
                    filtered_events.append(event)
                continue
            
            # Check source visibility
            sources = event.get("sources", [])
            is_public = True
            for source in sources:
                if get_source_visibility(source, config) == "private":
                    is_public = False
                    break
            
            if visibility == "public" and is_public:
                filtered_events.append(event)
            elif visibility == "private" and not is_public:
                filtered_events.append(event)
        
        if filtered_events:
            filtered_days.append({
                "day_name": day["day_name"],
                "date": day["date"],
                "events": filtered_events
            })
    
    return {"days": filtered_days, "generated": events_data.get("generated")}


if __name__ == "__main__":
    main()
