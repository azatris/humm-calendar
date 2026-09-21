# humm-calendar

Every 30 minutes a GitHub Action reads the public "Humm" Google Calendar, expands recurring events for the next 12 months, removes links and meeting passwords, and writes `docs/events.json`. GitHub Pages serves it to the humm.ee website. No API keys.
