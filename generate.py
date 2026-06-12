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
    },

    # ── NOUVELLES SOURCES (recommandées par l'équipe) ──
    {
        "name": "Conoship",
        "url": "https://www.conoship.com/feed/",
        "sectors": ["Shipping"]
    },
    {
        "name": "Gama Aviation",
        "url": "https://www.gamaaviation.com/feed/",
        "sectors": ["Aviation"]
    },
    {
        "name": "Omni Helicopters International",
        "url": "https://www.omnihelicoptersinternational.com/feed/",
        "sectors": ["Aviation"]
    },
    {
        "name": "SMFL Helicopters",
        "url": "https://smflh.aero/feed/",
        "sectors": ["Aviation"]
    },
    {
        "name": "Aerobuzz",
        "url": "https://www.aerobuzz.fr/feed/",
        "sectors": ["Aviation"]
    },
    {
        "name": "Journal de l'Aviation",
        "url": "https://www.journal-aviation.com/feed",
        "sectors": ["Aviation"]
    },
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

# ── MOTS-CLÉS NÉGATIFS (uniquement pour Aerobuzz) ──
# Aerobuzz couvre TOUTE l'actualité aéronautique française (30 articles/flux),
# y compris l'aviation de loisir, les ULM, et les meetings aériens — hors
# périmètre pour un fonds de PE infra. On exclut ces articles en plus du
# filtre par mots-clés positifs ci-dessus.
AEROBUZZ_EXCLUDE_KEYWORDS = [
    "ulm", "aéro-club", "aeroclub", "meeting aérien", "voltige",
    "aviation de loisir", "planeur", "parachut", "montgolfière",
    "rallye aérien", "fly-in", "fête aérienne"
]

# ── PARAMÈTRES DE SÉLECTION DES ARTICLES ──
# Nombre maximum d'articles retenus par source (anti-monopole) :
# évite qu'une grosse source (ex: Reuters) sature la liste avant
# même que les sources spécialisées (Conoship, SMFL...) ne soient lues.
MAX_ARTICLES_PER_SOURCE = 3

# Nombre total d'articles envoyés à Groq, et quota minimum garanti
# par secteur parmi ce total (cf. select_balanced_articles).
TOTAL_ARTICLES_FOR_GROQ = 20
SECTORS = ["Rail", "Aviation", "Shipping", "Engines"]
MIN_PER_SECTOR = 3  # 4 secteurs × 3 = 12 places "garanties" min, le reste (8) est libre

# Fenêtre temporelle : un article plus vieux que ça est ignoré, pour éviter
# de reprendre des actus déjà couvertes dans une édition précédente.
# 14 jours = un cycle de la newsletter bimensuelle.
# Comportement permissif : si la date de publication est absente ou
# illisible dans le flux, l'article est gardé quand même (mieux vaut
# un article potentiellement vieux qu'une source entière perdue).
MAX_ARTICLE_AGE_DAYS = 14

# ── CONTREPARTIES RIVE À SURVEILLER ──
# Noms nettoyés (sans formes juridiques GmbH/Ltd/SAS/AG/etc.) pour des
# requêtes Google News plus pertinentes. Pour les noms très génériques
# (Monti, VLO, PSL, HUBERT, Rail Unit...), un mot de contexte ("rail" /
# "logistics") a été ajouté pour éviter le bruit.
COUNTERPARTIES = [
    "KombiRail Europe",
    "LEG Leipziger Eisenbahnverkehrsgesellschaft",
    "LOCON Logistik Consulting",
    "Logix Aero",
    "Lufthansa Technik",
    "Mindener Kreisbahnen",
    "Monacair",
    "MTU Maintenance Lease Services",
    "Niederrheinische Verkehrsbetriebe NIAG",
    "OHI Finance",
    "Omni Taxi Aereo",
    "Pegasus Aviacion",
    "ProTrain Resurs",
    "RBP Rheinische Bahnpersonal",
    "RheinCargo",
    "Rhenus Rail St. Ingbert",
    "RTB Cargo Netherlands",
    "SAF Helicopteres",
    "SGL Schienen Güter Logistik",
    "SKL Schienen Komplex Logistik Magdeburg",
    "SLG Spitzke Logistik",
    "SPL Eisenbahnverkehr",
    "Titan Helicopters",
    "TRIANGULA Logistik",
    "Ultimate Heli",
    "WFL Wedler Franz Logistik",
    "Wiking Helikopter Service",
    "zl-traktion",
    "Monti rail",
    "Heli Service International",
    "Uni-Fly Heliworx",
    "Brilog Leasing",
    "North Star Shipping Aberdeen",
    "SBB Cargo",
    "RFO Rail Force One",
    "Hubert rail logistics",
    "Schweerbau",
    "VLO rail",
    "Rail Unit logistics",
    "Hering HBD",
    "PSL rail logistics",
    "SWEG Südwestdeutsche Landesverkehrs",
    "Siemens Mobility",
    "Willke Logistics",
    "Cargo Logistik Rail Service",
    "Diepholzer Kreisbahn ErailS",
    "CFL cargo Deutschland",
    "Train4Train",
    "smart rail",
]

# Nombre maximum d'articles "Counterparties Watch" retenus au total
# avant envoi à Groq (évite de surcharger le prompt).
MAX_COUNTERPARTY_ARTICLES = 4

# Modèle d'URL Google News RSS — recherche en anglais par défaut.
GOOGLE_NEWS_RSS_TEMPLATE = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"


# ============================================================
# HELPER — VÉRIFICATION DE FRAÎCHEUR D'UN ARTICLE
# ============================================================
def is_recent_enough(entry):
    """
    Retourne True si l'article a été publié dans les MAX_ARTICLE_AGE_DAYS
    derniers jours.

    Comportement permissif : si le flux RSS ne fournit pas de date de
    publication exploitable (champ absent ou illisible), on retourne
    True par défaut — on préfère garder un article potentiellement
    vieux plutôt que de perdre une source entière à cause d'un flux
    mal formé.
    """
    published = entry.get("published_parsed") or entry.get("updated_parsed")

    if not published:
        return True  # date inconnue → on garde par défaut

    try:
        published_date = datetime.datetime(*published[:6])
    except (TypeError, ValueError):
        return True  # date illisible → on garde par défaut

    age = datetime.datetime.now() - published_date
    return age.days <= MAX_ARTICLE_AGE_DAYS


# ============================================================
# ÉTAPE 1A — COLLECTE RSS
# ============================================================
def collect_articles():
    """
    Parcourt chaque source RSS et filtre les articles pertinents.
    Conserve le lien de chaque article pour les URLs sources.
    """
    articles = []

    for source in SOURCES:
        print(f"  → Lecture de {source['name']}...")
        source_count = 0  # nombre d'articles retenus pour cette source
        try:
            feed = feedparser.parse(source["url"])

            for entry in feed.entries:
                # Anti-monopole : une source ne fournit pas plus de
                # MAX_ARTICLES_PER_SOURCE articles, pour laisser de la
                # place aux sources plus petites/spécialisées.
                if source_count >= MAX_ARTICLES_PER_SOURCE:
                    break

                # Filtre de fraîcheur : ignore les articles trop anciens
                # (probablement déjà couverts dans une édition précédente).
                if not is_recent_enough(entry):
                    continue

                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "")
                text = (title + " " + summary).lower()

                is_relevant = any(kw.lower() in text for kw in KEYWORDS)

                # Filtre additionnel pour Aerobuzz : exclut l'aviation
                # de loisir / ULM / meetings aériens, hors périmètre PE.
                if is_relevant and source["name"] == "Aerobuzz":
                    if any(ex_kw.lower() in text for ex_kw in AEROBUZZ_EXCLUDE_KEYWORDS):
                        is_relevant = False

                if is_relevant:
                    articles.append({
                        "source": source["name"],
                        "title": title,
                        "summary": summary,
                        "link": link,
                        "sectors": source["sectors"]
                    })
                    source_count += 1

        except Exception as e:
            print(f"  ⚠ Erreur sur {source['name']} : {e}")
            continue

    print(f"\n  ✓ {len(articles)} articles collectés via RSS")

    # Répartition par secteur (un article peut compter dans plusieurs
    # secteurs s'il est issu d'une source multi-secteurs comme Reuters)
    sector_counts = {sector: 0 for sector in SECTORS}
    for article in articles:
        for sector in article["sectors"]:
            if sector in sector_counts:
                sector_counts[sector] += 1
    repartition = " · ".join(f"{s}: {c}" for s, c in sector_counts.items())
    print(f"  Répartition : {repartition}")

    return articles


# ============================================================
# ÉTAPE 1A-BIS — SÉLECTION ÉQUILIBRÉE PAR SECTEUR
# ============================================================
def select_balanced_articles(articles):
    """
    Réduit la liste d'articles collectés à TOTAL_ARTICLES_FOR_GROQ
    en garantissant un minimum d'articles par secteur (MIN_PER_SECTOR),
    avant de combler le reste avec les articles restants dans l'ordre
    de collecte (donc en respectant approximativement l'ordre des flux).

    Un article peut couvrir plusieurs secteurs (ex: Reuters Business),
    il est alors éligible au quota de chacun de ces secteurs mais n'est
    ajouté qu'une seule fois à la liste finale.
    """
    if len(articles) <= TOTAL_ARTICLES_FOR_GROQ:
        return articles

    selected = []
    selected_ids = set()  # index dans `articles` déjà choisis

    # ── Étape A : quota minimum garanti par secteur ──
    for sector in SECTORS:
        count_for_sector = 0
        for i, article in enumerate(articles):
            if count_for_sector >= MIN_PER_SECTOR:
                break
            if i in selected_ids:
                continue
            if sector in article["sectors"]:
                selected.append(article)
                selected_ids.add(i)
                count_for_sector += 1

    # ── Étape B : remplissage avec le reste, dans l'ordre de collecte ──
    for i, article in enumerate(articles):
        if len(selected) >= TOTAL_ARTICLES_FOR_GROQ:
            break
        if i not in selected_ids:
            selected.append(article)
            selected_ids.add(i)

    print(f"  ✓ {len(selected)} articles sélectionnés pour Groq "
          f"(sur {len(articles)} collectés, min {MIN_PER_SECTOR}/secteur)")
    return selected[:TOTAL_ARTICLES_FOR_GROQ]


# ============================================================
# ÉTAPE 1C — NEWS DES CONTREPARTIES (Google News RSS)
# ============================================================
def collect_counterparty_news():
    """
    Pour chaque contrepartie de COUNTERPARTIES, interroge le flux
    Google News RSS correspondant et garde le 1er article pertinent
    (le plus récent, filtré par fraîcheur MAX_ARTICLE_AGE_DAYS).

    Retourne au maximum MAX_COUNTERPARTY_ARTICLES articles au total,
    et affiche une répartition par contrepartie (combien d'articles
    trouvés pour chacune, avant troncature finale).
    """
    import urllib.parse

    found_articles = []
    counts_per_counterparty = {}

    for name in COUNTERPARTIES:
        counts_per_counterparty[name] = 0
        query = urllib.parse.quote(f'"{name}"')
        url = GOOGLE_NEWS_RSS_TEMPLATE.format(query=query)

        try:
            feed = feedparser.parse(url)

            for entry in feed.entries:
                if not is_recent_enough(entry):
                    continue

                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "")

                found_articles.append({
                    "counterparty": name,
                    "title": title,
                    "summary": summary,
                    "link": link,
                })
                counts_per_counterparty[name] += 1
                break  # un seul article par contrepartie

        except Exception as e:
            print(f"  ⚠ Erreur sur {name} : {e}")
            continue

    total_found = sum(counts_per_counterparty.values())
    print(f"\n  ✓ {total_found} articles trouvés sur {len(COUNTERPARTIES)} contreparties")
    repartition = " · ".join(f"{name}: {c}" for name, c in counts_per_counterparty.items())
    print(f"  Répartition : {repartition}")

    # Limite finale avant envoi à Groq
    selected = found_articles[:MAX_COUNTERPARTY_ARTICLES]
    print(f"  ✓ {len(selected)} articles retenus pour la section Counterparties Watch")
    return selected


# ============================================================
# ÉTAPE 1B — LECTURE DU FICHIER MANUEL
# ============================================================
def read_manual_input():
    """
    Lit le fichier manual_input.txt et retourne son contenu.
    Ignore les lignes qui commencent par # (commentaires).
    """
    if not os.path.exists("manual_input.txt"):
        return ""

    with open("manual_input.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()

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
# ÉTAPE 2 — GÉNÉRATION PAR GROQ
# ============================================================
def generate_newsletter(articles, manual_content="", counterparty_articles=None):
    """
    Envoie les articles et le contenu manuel à Groq
    pour générer la newsletter en JSON structuré avec liens sources.
    """
    if counterparty_articles is None:
        counterparty_articles = []

    # Résumé des articles RSS avec leurs liens
    # (la liste `articles` est déjà bornée par select_balanced_articles)
    articles_text = ""
    for i, a in enumerate(articles):
        articles_text += f"\n[{i+1}] {a['title']} ({a['source']})\n"
        articles_text += f"URL: {a['link']}\n"
        articles_text += f"{a['summary']}\n"

    # Section manuelle si elle existe
    manual_section = ""
    if manual_content:
        manual_section = f"""
ADDITIONAL INFORMATION (added manually by the editor — treat as high priority):
{manual_content}
"""

    # Articles concernant les contreparties de Rive (Google News RSS)
    counterparty_text = ""
    if counterparty_articles:
        counterparty_text = "\nNEWS ABOUT RIVE'S COUNTERPARTIES (operators, lessees, partners):\n"
        for i, a in enumerate(counterparty_articles):
            counterparty_text += f"\n[{i+1}] {a['title']} (about: {a['counterparty']})\n"
            counterparty_text += f"URL: {a['link']}\n"
            counterparty_text += f"{a['summary']}\n"

    prompt = f"""
You are the editor of "Rive Private Investment Market Intelligence",
a professional biweekly newsletter for a private investment firm
focused on European transport infrastructure assets.

Sectors covered: Rail, Aviation (aircraft & helicopters), Shipping (maritime), Aircraft Engines.
Focus: Europe primarily.
Audience: senior investment professionals, very busy, need concise sharp insights.

Based on these recent news articles (each with its URL):
{articles_text}
{manual_section}
{counterparty_text}

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
      "summary": "2-3 sentences on what happened and why it matters for investors",
      "source": "Publication name",
      "source_url": "exact URL of the source article, or empty string if unknown"
    }}
  ],
  "macro_stories": [
    {{
      "tag": "REGULATION|MARKET|GEOPOLITICS|INFRASTRUCTURE|TECHNOLOGY",
      "title": "Story headline — sharp and specific",
      "body": "2-3 sentences with clear investment angle or implication",
      "source": "Publication name",
      "source_url": "exact URL of the source article, or empty string if unknown"
    }}
  ],
  "counterparty_news": [
    {{
      "counterparty": "Name of the counterparty company this news is about",
      "title": "Story headline — sharp and specific",
      "body": "1-2 sentences summarizing the news and its relevance to Rive as an investor/lender to this counterparty",
      "source": "Publication name",
      "source_url": "exact URL of the source article, or empty string if unknown"
    }}
  ]
}}

Rules:
- 3 to 6 deals maximum, only genuine transactions (M&A, fundraising, infrastructure investment)
- 2 to 4 macro stories maximum
- 0 to 4 counterparty_news items — only include genuinely newsworthy items (operational changes,
  financial events, leadership changes, contracts, incidents); omit if the article is trivial
  (e.g. routine job postings) rather than inventing relevance
- Every sentence must add value — no filler, no generic statements
- Always include the investment angle or implication
- Sharp professional English, active voice
- If news is insufficient for a sector, omit rather than invent
- Prioritize manually added content if provided
- Use the article URLs provided above as source_url values where relevant
"""

    print("  → Envoi à Groq...")
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
    print("  ✓ Newsletter générée par Groq")
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
        if "source" not in deal:
            deal["source"] = "Rive Research"
        if "source_url" not in deal:
            deal["source_url"] = ""
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
    sous forme de fichier JSON et crée la page HTML correspondante.
    """
    import shutil

    os.makedirs("archives", exist_ok=True)

    today_display = datetime.date.today().strftime("%d %B %Y").upper()
    archive_data = {
        "edition_label": f"EDITION #{edition_number:02d} — {today_display}",
        "edition_title": content["edition_title"],
        "deals": content["deals"],
        "macro_stories": content["macro_stories"],
        "counterparty_news": content.get("counterparty_news", [])
    }

    # Sauvegarde le JSON
    json_path = f"archives/edition-{edition_number:02d}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(archive_data, f, ensure_ascii=False, indent=2)

    # Crée la page HTML à partir du template edition-01.html
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
    Met à jour le hero, les deals, les macros et l'archive dans index.html.
    """
    today_display = datetime.date.today().strftime("%d %B %Y").upper()

    # ── HTML des deals avec liens sources ──
    deals_html = ""
    for d in content["deals"]:
        source_html = ""
        if d.get("source_url"):
            source_html = f'<a href="{d["source_url"]}" target="_blank" class="source-link">↗ {d.get("source", "Source")}</a>'
        elif d.get("source"):
            source_html = f'<span class="source-label">{d["source"]}</span>'

        deals_html += f"""
      <div class="deal-card">
        <span class="deal-sector-badge badge-{d['sector']}">{d['sector']}</span>
        <div class="deal-body">
          <div class="deal-title">{d['title']}</div>
          <div class="deal-meta">{d['value']} · {d['geography']} · {d['type']}</div>
          {source_html}
        </div>
      </div>"""

    # ── HTML des macros avec liens sources ──
    macro_html = ""
    for m in content["macro_stories"]:
        source_html = ""
        if m.get("source_url"):
            source_html = f'<a href="{m["source_url"]}" target="_blank" class="source-link">↗ {m.get("source", "Source")}</a>'
        elif m.get("source"):
            source_html = f'<span class="source-label">{m["source"]}</span>'

        macro_html += f"""
      <div class="news-card">
        <div class="news-tag">{m['tag']}</div>
        <div class="news-title">{m['title']}</div>
        <div class="news-body">{m['body']}</div>
        {source_html}
      </div>"""

    # ── HTML des counterparty news avec liens sources ──
    counterparty_html = ""
    for c in content.get("counterparty_news", []):
        source_html = ""
        if c.get("source_url"):
            source_html = f'<a href="{c["source_url"]}" target="_blank" class="source-link">↗ {c.get("source", "Source")}</a>'
        elif c.get("source"):
            source_html = f'<span class="source-label">{c["source"]}</span>'

        counterparty_html += f"""
      <div class="news-card">
        <div class="news-tag">{c['counterparty']}</div>
        <div class="news-title">{c['title']}</div>
        <div class="news-body">{c['body']}</div>
        {source_html}
      </div>"""

    # ── Lecture du HTML ──
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

    # ── Mise à jour des macros ──
    html = re.sub(
        r'<!-- MACRO_START -->.*?<!-- MACRO_END -->',
        f'<!-- MACRO_START -->{macro_html}<!-- MACRO_END -->',
        html,
        flags=re.DOTALL
    )

    # ── Mise à jour des counterparty news ──
    html = re.sub(
        r'<!-- COUNTERPARTIES_START -->.*?<!-- COUNTERPARTIES_END -->',
        f'<!-- COUNTERPARTIES_START -->{counterparty_html}<!-- COUNTERPARTIES_END -->',
        html,
        flags=re.DOTALL
    )

    # ── Ajout à l'archive ──
    new_archive_card = f"""
    <div class="archive-card" onclick="window.location='archives/edition-{edition_number:02d}.html'">
      <div>
        <div class="archive-edition">EDITION #{edition_number:02d} — {today_display}</div>
        <div class="archive-title">{content["edition_title"]}</div>
        <div class="archive-meta">{len(content["deals"])} deals · {len(content["macro_stories"])} macro stories</div>
      </div>
      <span class="archive-arrow">→</span>
    </div>"""

    html = html.replace(
        '<div id="archive-list">',
        f'<div id="archive-list">{new_archive_card}'
    )

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
    articles = select_balanced_articles(articles)
    manual_content = read_manual_input()

    print("\n  → Collecte des news sur les contreparties...")
    counterparty_articles = collect_counterparty_news()

    if not articles and not manual_content:
        print("  ⚠ Aucun contenu collecté. Vérifie ta connexion.")
        return

    print("\n[2/4] Génération par Groq...")
    content = generate_newsletter(articles, manual_content, counterparty_articles)

    print("\n[3/4] Mise à jour des fichiers...")
    total_deals = update_deals_json(content["deals"])

    # Numéro d'édition
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