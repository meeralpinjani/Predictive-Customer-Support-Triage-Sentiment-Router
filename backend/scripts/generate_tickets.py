import csv
from pathlib import Path
import random

SEED = 42
random.seed(SEED)

TEMPLATES = [
    # Critical Outage (high urgency, high/low frustration, critical=1)
    ("Our production dashboard is DOWN. We will cancel if this is not fixed ASAP!", "high", "high", 1, "outage"),
    ("Production server is down and rejecting all user logins.", "high", "low", 1, "outage"),
    ("Emergency: Complete site outage. All transactions are failing immediately.", "high", "high", 1, "outage"),
    ("The database cluster is down and throwing 500 errors across all clients.", "high", "high", 1, "outage"),
    ("Production website has been down for 30 minutes. We are losing business!", "high", "high", 1, "outage"),
    ("Our api platform is down right now, need urgent resolution.", "high", "low", 1, "outage"),

    # Critical Security (high urgency, critical=1)
    ("Someone logged in to my account from another country. Was there a breach?", "high", "low", 1, "security"),
    ("Unauthorized access detected on our company admin dashboard.", "high", "high", 1, "security"),
    ("We suspect an account takeover. Stolen credentials and unauthorized changes.", "high", "high", 1, "security"),
    ("Phishing attack detected targeting our employee credentials.", "high", "low", 1, "security"),
    ("Our private security tokens have been compromised and breached.", "high", "high", 1, "security"),

    # Critical Legal (high urgency, critical=1)
    ("Our corporate counsel has advised legal action and a lawsuit regarding SLA breach.", "high", "high", 1, "legal"),
    ("Our attorney will sue you in court if our data is not exported today.", "high", "high", 1, "legal"),
    ("Notice of legal lawsuit regarding unauthorized billing charges.", "high", "high", 1, "legal"),
    ("We have engaged a lawyer and will report this to the federal regulator.", "high", "high", 1, "legal"),

    # Critical Safety (high urgency, critical=1)
    ("The power backup hardware started smoking and overheating. It is unsafe!", "high", "high", 1, "safety"),
    ("Electric shock hazard from the supplied power connector unit.", "high", "high", 1, "safety"),
    ("Worker injury due to defective equipment casing hazard.", "high", "high", 1, "safety"),

    # Billing Disputes (medium urgency, low/high frustration, critical=0)
    ("I was charged twice this month. Please refund today.", "medium", "low", 0, "billing_dispute"),
    ("Double charge on our credit card statement. Need refund immediately.", "medium", "medium", 0, "billing_dispute"),
    ("We were billed after cancelling. This is ridiculous, refund our money.", "medium", "high", 0, "billing_dispute"),
    ("Wrong charge on invoice #9021. Please review and credit account.", "medium", "low", 0, "billing_dispute"),
    ("Duplicate payment went through on our renewal invoice.", "medium", "low", 0, "billing_dispute"),
    ("Why was my account charged $199 instead of $99? Terrible service.", "medium", "high", 0, "billing_dispute"),

    # Routine Password Reset (low urgency, low frustration, critical=0)
    ("How do I reset my password?", "low", "low", 0, "password_reset"),
    ("Forgot my password and recovery link is not arriving.", "low", "low", 0, "password_reset"),
    ("Where can I reset my account login password?", "low", "low", 0, "password_reset"),
    ("Need assistance with password reset on mobile app.", "low", "low", 0, "password_reset"),

    # Routine Invoices & Billing History (low urgency, low frustration, critical=0)
    ("Where can I download my invoice for September?", "low", "low", 0, "invoice"),
    ("Need PDF receipt of our last payment for accounting records.", "low", "low", 0, "invoice"),
    ("How to access past billing history and VAT tax invoices?", "low", "low", 0, "invoice"),
    ("Please send the annual invoice receipt to our finance department.", "low", "low", 0, "invoice"),

    # Routine How-to / Account (low urgency, low frustration, critical=0)
    ("How do I invite additional team members to our workspace?", "low", "low", 0, "how_to"),
    ("Where do I find the setting to update my email address?", "low", "low", 0, "how_to"),
    ("How to configure two-factor authentication on mobile?", "low", "low", 0, "how_to"),
    ("Where can we export our workspace logs and activity history?", "low", "low", 0, "how_to"),
    ("How to change our company notification email preferences?", "low", "low", 0, "how_to"),

    # Bug reports (medium urgency, low/high frustration, critical=0)
    ("The CSV export feature crashes whenever exporting more than 100 rows.", "medium", "low", 0, "bug"),
    ("Mobile app crashes on startup when opening the notification tab.", "medium", "low", 0, "bug"),
    ("We are getting unexpected 500 error when submitting the profile form.", "medium", "low", 0, "bug"),
    ("Search filters are broken and do not return any matching records.", "medium", "low", 0, "bug"),
    ("Slow performance on dashboard during peak European hours.", "medium", "medium", 0, "bug"),

    # High Frustration Complaints (medium urgency, high frustration, critical=0)
    ("This is the worst app, nothing works and nobody replies!!!", "medium", "high", 0, "bug"),
    ("Nobody answered our ticket for 3 days. This service is utterly useless and unacceptable.", "medium", "high", 0, "complaint"),
    ("Furious with this terrible tool, nothing works and I am fed up with the bugs.", "medium", "high", 0, "complaint"),
    ("Unacceptable delays, ridiculous customer service, nobody helps us.", "medium", "high", 0, "complaint"),

    # Cancellations (low/medium urgency, critical=0)
    ("I want to cancel my subscription and close my account next month.", "low", "low", 0, "cancellation"),
    ("Please cancel my subscription and close my account. Switching to competitor.", "medium", "medium", 0, "cancellation"),
    ("We decided to cancel our pro plan and request confirmation.", "low", "low", 0, "cancellation"),

    # Feature requests (low urgency, low frustration, critical=0)
    ("Would be nice to have dark mode in the web app.", "low", "low", 0, "feature_request"),
    ("Feature request: please add custom logo uploads to PDF export reports.", "low", "low", 0, "feature_request"),
    ("Suggestion: would love keyboard shortcuts for navigating tickets.", "low", "low", 0, "feature_request"),
    ("Please add support for webhook event triggers on status update.", "low", "low", 0, "feature_request"),
]


def generate_labelled_dataset(output_path: Path, target_count: int = 220) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []

    # Multiply and perturb templates to reach target_count
    idx = 0
    while len(rows) < target_count:
        item = TEMPLATES[idx % len(TEMPLATES)]
        text, urg, fr, crit, intent = item
        # Add slight realistic suffix variation on repeats
        if len(rows) >= len(TEMPLATES):
            suffixes = [
                " Please assist.",
                " Thanks in advance.",
                " Need update ASAP.",
                " Looking forward to your reply.",
                " Critical for our team.",
                " Thank you.",
            ]
            text = text + suffixes[len(rows) % len(suffixes)]

        rows.append({
            "text": text,
            "urgency_label": urg,
            "frustration_label": fr,
            "critical": crit,
            "intent": intent,
        })
        idx += 1

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "urgency_label", "frustration_label", "critical", "intent"])
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


if __name__ == "__main__":
    out_file = Path(__file__).resolve().parent.parent / "data" / "tickets_labelled.csv"
    count = generate_labelled_dataset(out_file, 220)
    print(f"Generated {count} labelled tickets in {out_file}")
