# ============================================================
# generate.py — Générateur de newsletter Rive Private Investment
# Version finale avec ajout manuel
# ============================================================

import json
import os
import datetime
import feedparser
import requests
import subprocess
import re
from dotenv import load_dotenv
from groq import Groq

# ── CONFIGURATION ──
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ── SOURCES RSS ──
SOURCES = [
    {
        "name": "Reuters Business",
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "sectors": ["Rail", "Aviation", "Shipping", "Engines"]
    },
    {
        "name": "FlightGlobal",
        "url": "https://www.flightglobal.com/rss/news",
        "sectors": ["Aviation", "Engines"]
    },
    {
        "name": "Railway Gazette",
        "url": "https://www.railwaygazette.com/feed",
        "sectors": ["Rail"]
    },
    {
        "name": "Seatrade Maritime",
        "url": "https://www.seatrade-maritime.com/rss.xml",
        "sectors": ["Shipping"]
    },
    {
        "name": "Splash247",
        "url": "https://splash247.com/feed/",
        "sectors": ["Shipping"]
    },
    {
        "name": "Aviation Week",
        "url": "https://aviationweek.com/rss.xml",
        "sectors": ["Aviation", "Engines"]
    },
    {
        "name": "International Railway Journal",
        "url": "https://www.railjournal.com/feed",
        "sectors": ["Rail"]
    }
]

# ── MOTS-CLÉS ──
KEYWORDS = [
    "rail", "railway", "train", "rolling stock", "locomotive", "tram",
    "aviation", "aircraft", "airline", "helicopter", "lessor", "leasing",
    "airbus", "boeing", "atr",
    "shipping", "maritime", "vessel", "fleet", "port", "container",
    "tanker", "bulk carrier", "feeder",
    "engine", "turbofan", "MRO", "CFM", "Safran", "MTU", "Rolls-Royce",
    "GE Aviation", "Pratt",
    "acquisition", "merger", "acquires", "M&A", "investment", "raises",
    "bond", "lease", "sale-leaseback", "joint venture", "JV", "fund",
    "Europe", "European", "EU", "France", "Germany", "UK", "Netherlands",
    "Spain", "Italy", "Nordic", "Poland", "Scandinavia"
]


# ============================================================
# ÉTAPE 1A — COLLECTE RSS
# ============================================================
def collect_articles():
    """
    Parcourt chaque source RSS et filtre les articles pertinents.
    """
    articles = []

    for source in SOURCES:
        print(f"  → Lecture de {source['name']}...")
        try:
            feed = feedparser.parse(source["url"])

            for entry in feed.entries:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                text = (title + " " + summary).lower()

                is_relevant = any(kw.lower() in text for kw in KEYWORDS)

                if is_relevant:
                    articles.append({
                        "source": source["name"],
                        "title": title,
                        "summary": summary,
                        "link": entry.get("link", ""),
                        "sectors": source["sectors"]
                    })

        except Exception as e:
            print(f"  ⚠ Erreur sur {source['name']} : {e}")
            continue

    print(f"\n  ✓ {len(articles)} articles collectés via RSS")
    return articles


# ============================================================
# ÉTAPE 1B — LECTURE DU FICHIER MANUEL
# ============================================================
def read_manual_input():
    """
    Lit le fichier manual_input.txt et retourne son contenu.
    Ignore les lignes qui commencent par # (commentaires).
    Vide le fichier après lecture pour éviter les doublons.
    """
    if not os.path.exists("manual_input.txt"):
        return ""

    with open("manual_input.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()

    # On garde uniquement les lignes qui ne sont pas des commentaires
    content_lines = [
        line for line in lines
        if not line.strip().startswith("#") and line.strip() != ""
    ]

    manual_content = "".join(content_lines).strip()

    if manual_content:
        print(f"  ✓ Contenu manuel trouvé ({len(content_lines)} lignes)")
    else:
        print(f"  → Pas de contenu manuel cette édition")

    return manual_content


# ============================================================
# ÉTAPE 2 — GÉNÉRATION PAR GEMINI
# ============================================================
def generate_newsletter(articles, manual_content=""):
    """
    Envoie les articles et le contenu manuel à Gemini
    pour générer la newsletter en JSON structuré.
    """
    # Résumé des articles RSS
    articles_text = ""
    for i, a in enumerate(articles[:20]):
        articles_text += f"\n[{i+1}] {a['title']} ({a['source']})\n{a['summary']}\n"

    # Section manuelle si elle existe
    manual_section = ""
    if manual_content:
        manual_section = f"""
ADDITIONAL INFORMATION (added manually by the editor — treat as high priority):
{manual_content}
"""

    prompt = f"""
You are the editor of "Rive Private Investment Market Intelligence",
a professional biweekly newsletter for a private investment firm
focused on European transport infrastructure assets.

Sectors covered: Rail, Aviation (aircraft & helicopters), Shipping (maritime), Aircraft Engines.
Focus: Europe primarily.
Audience: senior investment professionals, very busy, need concise sharp insights.

Based on these recent news articles:
{articles_text}
{manual_section}

Generate a newsletter in this EXACT JSON format (pure JSON only, no markdown, no backticks):
{{
  "edition_title": "A compelling 8-10 word headline summarizing the key theme this fortnight",
  "deals": [
    {{
      "title": "Deal title with company names and action verb",
      "sector": "Rail|Aviation|Shipping|Engines",
      "type": "M&A|Debt Raise|Infrastructure|Equity|IPO|Other",
      "value": "€XM or Unknown",
      "geography": "Country or Region",
      "summary": "2-3 sentences on what happened and why it matters for investors"
    }}
  ],
  "macro_stories": [
    {{
      "tag": "REGULATION|MARKET|GEOPOLITICS|INFRASTRUCTURE|TECHNOLOGY",
      "title": "Story headline — sharp and specific",
      "body": "2-3 sentences with clear investment angle or implication"
    }}
  ]
}}

Rules:
- 3 to 6 deals maximum, only genuine transactions (M&A, fundraising, infrastructure investment)
- 2 to 4 macro stories maximum
- Every sentence must add value — no filler, no generic statements
- Always include the investment angle or implication
- Sharp professional English, active voice
- If news is insufficient for a sector, omit rather than invent
- Prioritize manually added content if provided
"""

    print("  → Envoi à Gemini...")
    response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.7
)

    # Nettoyage de la réponse
    text = response.choices[0].message.content.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    data = json.loads(text)
    print("  ✓ Newsletter générée par Gemini")
    return data


# ============================================================
# ÉTAPE 3 — MISE À JOUR DE DEALS.JSON
# ============================================================
def update_deals_json(new_deals):
    """
    Ajoute les nouveaux deals en tête de la base existante.
    """
    with open("deals.json", "r", encoding="utf-8") as f:
        existing = json.load(f)

    next_id = max([d["id"] for d in existing["deals"]], default=0) + 1
    today = datetime.date.today().isoformat()

    for deal in new_deals:
        deal["id"] = next_id
        deal["date"] = today
        # On ajoute le champ source s'il manque
        if "source" not in deal:
            deal["source"] = "Rive Research"
        existing["deals"].insert(0, deal)
        next_id += 1

    with open("deals.json", "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"  ✓ {len(new_deals)} nouveaux deals ajoutés à deals.json")
    return len(existing["deals"])

# ============================================================
# ÉTAPE 3B — SAUVEGARDE DE L'ARCHIVE
# ============================================================
def save_archive(content, edition_number):
    """
    Sauvegarde le contenu de l'édition dans archives/
    sous forme de fichier JSON et copie le template HTML.
    """
    import shutil

    # Crée le dossier archives s'il n'existe pas
    os.makedirs("archives", exist_ok=True)

    # Sauvegarde le JSON de l'édition
    today_display = datetime.date.today().strftime("%d %B %Y").upper()
    archive_data = {
        "edition_label": f"EDITION #{edition_number:02d} — {today_display}",
        "edition_title": content["edition_title"],
        "deals": content["deals"],
        "macro_stories": content["macro_stories"]
    }

    json_path = f"archives/edition-{edition_number:02d}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(archive_data, f, ensure_ascii=False, indent=2)

    # Copie le template HTML en remplaçant le numéro d'édition
    template_path = "archives/edition-01.html"
    new_html_path = f"archives/edition-{edition_number:02d}.html"

    if os.path.exists(template_path) and not os.path.exists(new_html_path):
        with open(template_path, "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace("edition-01.json", f"edition-{edition_number:02d}.json")
        with open(new_html_path, "w", encoding="utf-8") as f:
            f.write(html)

    print(f"  ✓ Archive edition-{edition_number:02d} sauvegardée")

# ============================================================
# ÉTAPE 4 — MISE À JOUR DE INDEX.HTML
# ============================================================
def update_index_html(content, edition_number, total_deals):
    """
    Met à jour le hero, les deals et les articles macro dans index.html.
    Met aussi à jour l'archive avec la nouvelle édition.
    """
    today_display = datetime.date.today().strftime("%d %B %Y").upper()
    today_iso = datetime.date.today().isoformat()

    # ── HTML des deals pour la newsletter ──
    deals_html = ""
    for d in content["deals"]:
        deals_html += f"""
      <div class="deal-card">
        <span class="deal-sector-badge badge-{d['sector']}">{d['sector']}</span>
        <div class="deal-body">
          <div class="deal-title">{d['title']}</div>
          <div class="deal-meta">{d['value']} · {d['geography']} · {d['type']}</div>
        </div>
      </div>"""

    # ── HTML des articles macro ──
    macro_html = ""
    for m in content["macro_stories"]:
        macro_html += f"""
      <div class="news-card">
        <div class="news-tag">{m['tag']}</div>
        <div class="news-title">{m['title']}</div>
        <div class="news-body">{m['body']}</div>
      </div>"""

    # ── Lecture du fichier HTML ──
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()

    # ── Mise à jour du hero ──
    html = re.sub(
        r'<div class="hero-edition">.*?</div>',
        f'<div class="hero-edition">EDITION #{edition_number:02d} — {today_display}</div>',
        html
    )
    html = re.sub(
        r'<div class="hero-title">.*?</div>',
        f'<div class="hero-title">{content["edition_title"]}</div>',
        html
    )
    html = re.sub(
        r'<div class="hero-meta">.*?</div>',
        f'<div class="hero-meta">{len(content["deals"])} deals tracked <span>·</span> {len(content["macro_stories"])} macro stories <span>·</span> 4 sectors covered</div>',
        html
    )

    # ── Mise à jour des deals ──
    html = re.sub(
        r'<!-- DEALS_START -->.*?<!-- DEALS_END -->',
        f'<!-- DEALS_START -->{deals_html}<!-- DEALS_END -->',
        html,
        flags=re.DOTALL
    )

    # ── Mise à jour des articles macro ──
    html = re.sub(
        r'<!-- MACRO_START -->.*?<!-- MACRO_END -->',
        f'<!-- MACRO_START -->{macro_html}<!-- MACRO_END -->',
        html,
        flags=re.DOTALL
    )

    # ── Ajout à l'archive ──
    new_archive_card = f"""
    <div class="archive-card">
      <div>
        <div class="archive-edition">EDITION #{edition_number:02d} — {today_display}</div>
        <div class="archive-title">{content["edition_title"]}</div>
        <div class="archive-meta">{len(content["deals"])} deals · {len(content["macro_stories"])} macro stories</div>
      </div>
      <span class="archive-arrow">→</span>
    </div>"""

new_archive_card = f"""
    <div class="archive-card" onclick="window.location='archives/edition-{edition_number:02d}.html'">
      <div>
        <div class="archive-edition">EDITION #{edition_number:02d} — {today_display}</div>
        <div class="archive-title">{content["edition_title"]}</div>
        <div class="archive-meta">{len(content["deals"])} deals · {len(content["macro_stories"])} macro stories</div>
      </div>
      <span class="archive-arrow">→</span>
    </div>"""    

    # ── Sauvegarde ──
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("  ✓ index.html mis à jour")


# ============================================================
# ÉTAPE 5 — PUBLICATION SUR GITHUB
# ============================================================
def publish_to_github():
    """
    Envoie les fichiers modifiés sur GitHub Pages.
    """
    today = datetime.date.today().isoformat()
    commands = [
        ["git", "add", "."],
        ["git", "commit", "-m", f"Newsletter edition — {today}"],
        ["git", "push"]
    ]
    for cmd in commands:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ⚠ Erreur Git : {result.stderr}")
        else:
            print(f"  ✓ {' '.join(cmd)}")

    print("  ✓ Site mis à jour sur GitHub Pages")


# ============================================================
# PROGRAMME PRINCIPAL
# ============================================================
def main():
    print("\n" + "="*50)
    print("  RIVE NEWSLETTER GENERATOR")
    print("="*50)

    print("\n[1/4] Collecte des actualités...")
    articles = collect_articles()
    manual_content = read_manual_input()

    if not articles and not manual_content:
        print("  ⚠ Aucun contenu collecté. Vérifie ta connexion.")
        return

    print("\n[2/4] Génération par Gemini...")
    content = generate_newsletter(articles, manual_content)

    print("\n[3/4] Mise à jour des fichiers...")
    total_deals = update_deals_json(content["deals"])

    # Numéro d'édition basé sur le nombre de générations
    edition_number = 1
    if os.path.exists("edition_count.txt"):
        with open("edition_count.txt", "r") as f:
            edition_number = int(f.read().strip()) + 1
    with open("edition_count.txt", "w") as f:
        f.write(str(edition_number))

    save_archive(content, edition_number)
    update_index_html(content, edition_number, total_deals)

    print("\n[4/4] Publication sur GitHub...")
    publish_to_github()

    print("\n" + "="*50)
    print(f"  ✓ Edition #{edition_number} publiée avec succès !")
    print("="*50 + "\n")


if __name__ == "__main__":
    main()