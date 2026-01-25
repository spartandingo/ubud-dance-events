# Ubud Dance Events

A calendar feed for contact improv, ecstatic dance, and movement events in Ubud, Bali.

## 📲 Subscribe

**Subscribe URL (for calendar apps):**
```
webcal://YOUR_USERNAME.github.io/ubud-dance-events/ubud-dance-events.ics
```

Or visit the website: https://YOUR_USERNAME.github.io/ubud-dance-events/

## 🔧 How it works

1. **Data sources:** WhatsApp groups, Telegram groups/forums, Instagram (@paradisoubud)
2. **Daily updates:** A cron job fetches new messages and regenerates the calendar
3. **Pattern detection:** Identifies recurring weekly events automatically
4. **ICS feed:** Standard iCalendar format works with Apple Calendar, Google Calendar, Outlook, etc.

## 📅 What's included

- ~20 recurring weekly events (contact jams, ecstatic dance, classes)
- Special workshops and intensives
- Events marked as CONFIRMED or TENTATIVE based on announcement confidence

## 🤖 Built with

- [Clawdbot](https://github.com/clawdbot/clawdbot) - AI assistant
- Python scripts for data aggregation
- Telethon (Telegram API)
- wacli (WhatsApp CLI)
- Instaloader (Instagram)

---

*Replace `YOUR_USERNAME` with your actual GitHub username after deploying.*
