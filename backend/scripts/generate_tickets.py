"""Generate the labelled evaluation sets (playbook 6.5-6.6).

data/tickets_labelled.csv  - ~380 tickets labelled for urgency, frustration, intent, language
data/kb_eval.csv           - routine questions with the article that should answer them,
                             plus out-of-scope / non-routine texts that must not be auto-answered

Honest held-out split: whole *templates* go to train or test (70/30 per intent), and the tone
and urgency phrases are split too, so test tickets use sentences and phrasings that the rules
and thresholds were never tuned on.

Labelling guide (playbook 6.6):
- urgency: critical issues are high; a template's base level is raised medium -> high when the
  ticket adds a deadline / money-lost / blocked phrase. Questions stay low.
- frustration: polite or neutral tone = low, frustrated = medium, angry or sarcastic = high;
  complaints are at least medium.
"""
import csv
from pathlib import Path
import random

SEED = 42
DATA = Path(__file__).resolve().parent.parent / "data"

# (intent, base urgency, critical, language, [templates])
TEMPLATES: list[tuple[str, str, int, str, list[str]]] = [
    ("outage", "high", 1, "en", [
        "Our {system} is down and none of our users can log in.",
        "The {system} has been down for {dur} and every request times out.",
        "Complete outage on our side, the {system} is offline.",
        "The {system} is unreachable from all our offices since this morning.",
        "We have an outage: checkout is down and orders are failing.",
        "The API is down, all our integrations return 503.",
        "Production is down. Nothing loads for any customer.",
        "Nothing loads for any of our customers since 9am, the whole service is unavailable.",
    ]),
    ("security", "high", 1, "en", [
        "Someone logged into my account from another country last night.",
        "We noticed unauthorized changes to our admin settings.",
        "I think my account was hacked, my email address was changed.",
        "There are charges I did not make, this looks like fraud.",
        "Our API keys were compromised and used by someone else.",
        "I got a phishing email pretending to be from you and I clicked the link.",
        "My password was changed without my permission.",
        "There is a login from a device I don't recognise on my account.",
    ]),
    ("legal", "high", 1, "en", [
        "Our lawyer will contact you about the breach of our contract.",
        "If this is not resolved we will take legal action.",
        "We are filing a complaint with the consumer regulator.",
        "Our attorney has advised us to sue for the lost revenue.",
        "Please treat this message as a formal legal notice about our data.",
        "We will see you in court if our data is not returned.",
    ]),
    ("safety", "high", 1, "en", [
        "The charger you shipped started smoking under my desk.",
        "The device is overheating and smells of burning plastic.",
        "One of our staff got an electric shock from the docking station.",
        "The battery pack is swelling and looks like a fire hazard.",
        "A worker was injured by the sharp edge of the casing.",
        "Sparks came out of the power adapter when I plugged it in.",
    ]),
    ("billing_dispute", "medium", 0, "en", [
        "I was charged twice for my subscription this month.",
        "There is a double charge on our card statement for invoice {inv}.",
        "We were billed after we cancelled the plan.",
        "You charged us {amt} instead of {amt2}.",
        "A duplicate payment went through for our renewal.",
        "My payment failed but the money was still deducted from my account.",
        "I need a refund for the extra seats you billed by mistake.",
        "The amount on my bank statement does not match my plan price.",
    ]),
    ("access", "medium", 0, "en", [
        "I am locked out of my account after the update.",
        "I can't log in, it keeps saying my credentials are invalid.",
        "My account is suspended and I don't know why.",
        "Login is not working on the mobile app.",
        "The sign in page just reloads and never lets me in.",
        "I am unable to sign in since you changed the login page.",
    ]),
    ("cancellation", "medium", 0, "en", [
        "Please cancel our subscription at the end of the month.",
        "We want to close our account.",
        "We have decided not to renew our contract.",
        "We are switching to another provider next quarter.",
        "Please stop the automatic renewal and downgrade us to free.",
    ]),
    ("bug", "medium", 0, "en", [
        "The CSV export is not working, it gives an error.",
        "The app crashes every time I open the reports page.",
        "Search stopped working after yesterday's update.",
        "Uploading files fails with an error message.",
        "The dashboard charts are broken and show no data.",
        "Email notifications stopped arriving for new tickets.",
        "The calendar sync shows the wrong times for all events.",
        "The mobile app freezes on the home screen.",
    ]),
    ("complaint", "medium", 0, "en", [
        "Nobody has answered my ticket for three days.",
        "This is the third time I am writing about the same problem.",
        "Your support has been very slow and unhelpful lately.",
        "I have been waiting for a week for a simple answer.",
        "Every agent tells me something different and nothing gets fixed.",
    ]),
    ("how_to", "low", 0, "en", [
        "How do I export my data to CSV?",
        "Where can I change my notification settings?",
        "How can I invite a colleague to my workspace?",
        "How do I connect Slack to my account?",
        "Can I change the time zone shown on tickets?",
        "How do I enable two-factor authentication?",
        "Where do I find my API key?",
        "How do I update my credit card?",
        "What are your support hours?",
    ]),
    ("password_reset", "low", 0, "en", [
        "How do I reset my password?",
        "I forgot my password, what should I do?",
        "The password reset email never arrived.",
        "Can I change my password from the app?",
        "Where is the forgot password link?",
    ]),
    ("invoice", "low", 0, "en", [
        "Where can I download my invoices?",
        "I need a receipt for last month's payment.",
        "Can you send me a copy of invoice {inv}?",
        "I need to update the GST number on our invoices.",
        "Where can I see my billing history?",
    ]),
    ("feature_request", "low", 0, "en", [
        "Would be nice to have dark mode.",
        "Please add an export to Google Sheets.",
        "It would be great if the app supported keyboard shortcuts.",
        "Feature request: let us schedule reports by email.",
        "Could you add a Hindi language option?",
        "I wish there was a way to tag tickets by colour.",
    ]),
    # Hinglish (playbook 6.7 #8, 7.6)
    ("billing_dispute", "medium", 0, "hi-en", [
        "Mera payment fail ho gaya par paisa kat gaya, refund chahiye.",
        "Is mahine paise do baar kat gaye hain.",
        "Payment fail hua lekin bank se paisa deducted dikha raha hai.",
    ]),
    ("outage", "high", 1, "hi-en", [
        "Site band ho gaya hai, koi bhi login nahi kar pa raha.",
        "Hamara dashboard down hai subah se, kuch bhi load nahi ho raha.",
    ]),
    ("bug", "medium", 0, "hi-en", [
        "App kaam nahi kar raha, export pe error aa raha hai.",
        "Reports page khulte hi app crash ho jata hai.",
    ]),
    ("password_reset", "low", 0, "hi-en", [
        "Password bhool gaya, reset kaise kare?",
        "Mera password reset karna hai, link kahan hai?",
    ]),
    ("access", "medium", 0, "hi-en", [
        "Login nahi ho raha, account lock ho gaya hai.",
    ]),
    ("complaint", "medium", 0, "hi-en", [
        "Teen din se koi reply nahi aaya, bahut bura service hai.",
    ]),
]

SLOTS = {
    "system": ["dashboard", "website", "platform", "production server", "app", "portal"],
    "dur": ["an hour", "two hours", "30 minutes", "most of the morning"],
    "inv": ["#9021", "#10442", "INV-2291", "#77310"],
    "amt": ["$199", "$480", "Rs 12,000"],
    "amt2": ["$99", "$240", "Rs 6,000"],
}

# Phrase banks: even-indexed entries are used for train, odd-indexed for test.
TONES_EN = {
    "polite": ["Thanks in advance!", "Thank you for your help.", "Appreciate your support.", "Kind regards.",
               "Many thanks for looking into it.", "Cheers, and thanks."],
    "neutral": ["Please advise.", "Ticket ref {inv}.", "Let me know.", "", "Details are above.", "Please check."],
    "frustrated": ["This is getting frustrating.", "I'm quite disappointed, to be honest.",
                   "This has happened before and it's annoying.", "Not happy about this at all.",
                   "We still haven't heard back from anyone.", "Honestly this is a bit of a mess."],
    "angry": ["This is UNACCEPTABLE!!!", "Fix this NOW or we cancel!",
              "I am furious, this is the worst service ever!", "If this isn't sorted we are switching to a competitor!!",
              "Absolutely ridiculous. I'm fed up with you.", "WHAT IS GOING ON?? Sort it out!",
              "I'm done with you people, never again.", "Pathetic. I'll be leaving a one star review."],
    "sarcastic": ["Great, just great. Thanks for nothing.", "Oh wonderful, another 'quick fix' that broke everything.",
                  "Love how I pay for this and it never works.", "Yeah right, 'world class support'.",
                  "Bravo, truly outstanding service.", "So much for your 99.9% uptime promise."],
}
TONES_HI = {
    "polite": ["Please help kijiye, thank you.", "Dhanyavaad.", "Thanks bhai, please check karo.", "Shukriya."],
    "neutral": ["Please check karo.", "", "Details upar hai.", "Batao kya karna hai."],
    "frustrated": ["Bahut pareshan ho gaye hain.", "Yeh baar baar ho raha hai.", "Kuch toh karo yaar.",
                   "Ab tak koi jawab nahi aaya."],
    "angry": ["Bakwas service hai! Turant fix karo!!!", "Ghatiya support, hum cancel kar denge!",
              "Kya pagal bana rahe ho?? Abhi theek karo!", "Faltu service, ab switch kar rahe hain!!"],
    "sarcastic": ["Wah, kya service hai. Thanks for nothing.", "Great, phir se kharab ho gaya.",
                  "Bahut badhiya, har hafte yahi drama.", "Yeah right, best support ever."],
}
URGENT_EN = ["We need this fixed today.", "This is urgent.", "Please handle this ASAP.",
             "We have a deadline tomorrow.", "We are losing money every hour.",
             "Our team is completely blocked.", "Please respond immediately.",
             "This is critical for a client demo this afternoon."]
URGENT_HI = ["Aaj hi chahiye.", "Jaldi karo please.", "Kal tak theek hona chahiye.", "Turant dekho."]

FRUSTRATION_BY_TONE = {"polite": "low", "neutral": "low", "frustrated": "medium", "angry": "high", "sarcastic": "high"}

# --------------------------------------------------------------------------- KB eval set
# (text, expected article id or "none"). Phrasings differ from the KB's own example questions.
KB_EVAL: list[tuple[str, str]] = [
    ("how can I set a new password for my login", "kb_pass_01"),
    ("I don't remember my password anymore", "kb_pass_01"),
    ("where do I reset my password", "kb_pass_01"),
    ("password reset kaise karte hain", "kb_pass_01"),
    ("where do I get a copy of my invoice", "kb_inv_02"),
    ("I need last quarter's receipts for accounting", "kb_inv_02"),
    ("download all my old invoices", "kb_inv_02"),
    ("how to change the email address I log in with", "kb_email_03"),
    ("I want to use a different email for my account", "kb_email_03"),
    ("how do I move from basic to pro", "kb_plan_04"),
    ("change my plan to annual", "kb_plan_04"),
    ("what is the refund policy", "kb_refund_05"),
    ("how many days do refunds take", "kb_refund_05"),
    ("how do I turn on two factor", "kb_2fa_06"),
    ("set up an authenticator app for my login", "kb_2fa_06"),
    ("how can I get a backup of everything in my workspace", "kb_export_07"),
    ("export records as json", "kb_export_07"),
    ("where is my package", "kb_ship_08"),
    ("my hardware order has not arrived yet", "kb_ship_08"),
    ("I get too many emails from you, how to stop them", "kb_notify_09"),
    ("turn off push notifications", "kb_notify_09"),
    ("can I use a dark theme", "kb_theme_10"),
    ("how do I enable night mode", "kb_theme_10"),
    ("how do I delete my account forever", "kb_delete_11"),
    ("erase all my personal data", "kb_delete_11"),
    ("where do I create an api key", "kb_api_12"),
    ("rotate my developer token", "kb_api_12"),
    ("how to set up okta single sign on", "kb_sso_13"),
    ("configure saml for our company", "kb_sso_13"),
    ("change the billing address on my invoices", "kb_address_14"),
    ("update our vat number", "kb_address_14"),
    ("log me out from my other laptop", "kb_session_15"),
    ("show all devices where I'm signed in", "kb_session_15"),
    ("my account got locked after wrong attempts", "kb_login_16"),
    ("it says invalid credentials when I log in", "kb_login_16"),
    ("my credit card expired, how to add new card", "kb_card_17"),
    ("change the card you charge", "kb_card_17"),
    ("how do I add a new user to our team", "kb_team_18"),
    ("invite my coworker", "kb_team_18"),
    ("I got a new phone and my authenticator codes are gone", "kb_2fareset_19"),
    ("lost my 2fa device", "kb_2fareset_19"),
    ("do you have an iphone app", "kb_mobile_20"),
    ("is there an android version", "kb_mobile_20"),
    ("connect to slack", "kb_integr_21"),
    ("how to set up webhooks", "kb_integr_21"),
    ("what is the storage limit on free plan", "kb_limits_22"),
    ("how many api requests per day", "kb_limits_22"),
    ("when is your support team available", "kb_hours_23"),
    ("how fast do you reply to tickets", "kb_hours_23"),
    ("where are your servers located for gdpr", "kb_privacy_24"),
    ("I want a copy of my personal data", "kb_privacy_24"),
    ("change the interface language", "kb_lang_25"),
    ("tickets show the wrong time zone", "kb_lang_25"),
    ("do you offer a nonprofit discount", "kb_pricing_26"),
    ("how much is the pro plan", "kb_pricing_26"),
    # must NOT be answered automatically
    ("Our production dashboard is down for every user", "none"),
    ("Someone hacked my account and changed the email", "none"),
    ("I was charged twice and need my money back today", "none"),
    ("Is the company cafeteria serving vegan pizza on Thursdays?", "none"),
    ("Can you recommend a good laptop for video editing?", "none"),
    ("The export button crashes the whole app", "none"),
    ("Your support is terrible and nobody replies", "none"),
    ("We will take legal action if this continues", "none"),
    ("What is the weather in Stockholm tomorrow?", "none"),
    ("My order was delivered damaged and smoking", "none"),
    ("Who won the football match yesterday?", "none"),
    ("The reports page shows a 500 error since the update", "none"),
    ("Our team is locked out and losing money every hour", "none"),
    ("Please write me a poem about support tickets", "none"),
    ("The app freezes when I upload large files", "none"),
    ("We want to cancel because the product keeps breaking", "none"),
]


def _split_bank(bank: list[str], split: str) -> list[str]:
    part = [p for i, p in enumerate(bank) if (i % 2 == 0) == (split == "train")]
    return part or bank


def _fill(template: str, rng: random.Random) -> str:
    out = template
    for k, vals in SLOTS.items():
        out = out.replace("{" + k + "}", rng.choice(vals))
        out = out.replace("{" + k.capitalize() + "}", rng.choice(vals).capitalize())
    return out


def generate() -> tuple[list[dict], list[dict]]:
    rng = random.Random(SEED)

    # Template-level split: 70% train / 30% test within each (intent, language) group.
    tickets: list[dict] = []
    for g, (intent, base_urg, critical, lang, temps) in enumerate(TEMPLATES):
        order = list(range(len(temps)))
        rng.shuffle(order)
        n_test = max(1, round(0.3 * len(temps)))
        test_ids = set(order[:n_test])
        tones_bank = TONES_HI if lang == "hi-en" else TONES_EN
        urgent_bank = URGENT_HI if lang == "hi-en" else URGENT_EN

        for t_idx, template in enumerate(temps):
            split = "test" if t_idx in test_ids else "train"
            tones = rng.sample(list(FRUSTRATION_BY_TONE), 4)
            for tone in tones:
                body = _fill(template, rng)
                parts = [body]
                urg = base_urg
                if base_urg == "medium" and rng.random() < 0.4:
                    parts.append(rng.choice(_split_bank(urgent_bank, split)))
                    urg = "high"
                elif base_urg != "medium" and rng.random() < 0.25:
                    parts.append(rng.choice(_split_bank(urgent_bank, split)))
                tone_text = _fill(rng.choice(_split_bank(tones_bank[tone], split)), rng)
                if tone_text:
                    parts.append(tone_text)
                if tone == "polite" and rng.random() < 0.5:
                    parts.insert(0, rng.choice(["Hi team,", "Hello,", "Good morning,"] if lang == "en" else ["Namaste,", "Hello team,"]))
                frus = FRUSTRATION_BY_TONE[tone]
                if intent == "complaint" and frus == "low":
                    frus = "medium"
                tickets.append({
                    "text": " ".join(parts),
                    "urgency_label": urg,
                    "frustration_label": frus,
                    "critical": critical,
                    "intent": intent,
                    "language": lang,
                    "tone": tone,
                    "template_id": f"T{g:02d}-{t_idx:02d}",
                    "split": split,
                })

    kb_rows = []
    for i, (text, art) in enumerate(KB_EVAL):
        kb_rows.append({"text": text, "expected_article": art, "split": "val" if i % 2 == 0 else "test"})
    return tickets, kb_rows


def _write(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    tickets, kb_rows = generate()
    _write(DATA / "tickets_labelled.csv", tickets)
    _write(DATA / "kb_eval.csv", kb_rows)
    n_test = sum(1 for t in tickets if t["split"] == "test")
    print(f"tickets_labelled.csv: {len(tickets)} tickets ({len(tickets) - n_test} train / {n_test} test)")
    print(f"kb_eval.csv: {len(kb_rows)} rows")
