"""Ticket categories customers choose from, and the support level each one starts at.

Level 1 · General Support, Level 2 · Technical Support, Level 3 · Expert Escalation.
A category only sets the *starting* level: the router can escalate a ticket further
(critical flags, frustration, value, score, ageing) but never below its category.
Level 3 cannot be chosen; it is reached through escalation only.
"""

LEVELS: dict[str, dict] = {
    "level1": {"rank": 1, "name": "General Support"},
    "level2": {"rank": 2, "name": "Technical Support"},
    "level3": {"rank": 3, "name": "Expert Escalation"},
}

CATEGORIES: list[dict] = [
    {"id": "account", "label": "Account & login", "level": "level1"},
    {"id": "billing", "label": "Billing & payments", "level": "level1"},
    {"id": "plans", "label": "Plans & subscriptions", "level": "level1"},
    {"id": "howto", "label": "How-to / usage", "level": "level1"},
    {"id": "feedback", "label": "Feedback & feature ideas", "level": "level1"},
    {"id": "bug", "label": "Bug / something broken", "level": "level2"},
    {"id": "outage", "label": "Service down / outage", "level": "level2"},
    {"id": "integrations", "label": "Integrations & API", "level": "level2"},
    {"id": "data", "label": "Data import / export", "level": "level2"},
    {"id": "performance", "label": "Performance / slowness", "level": "level2"},
]
CATEGORY_BY_ID = {c["id"]: c for c in CATEGORIES}


def level_name(route: str) -> str:
    if route == "auto_kb":
        return "Answered automatically"
    lvl = LEVELS.get(route)
    return f"Level {lvl['rank']} · {lvl['name']}" if lvl else route
