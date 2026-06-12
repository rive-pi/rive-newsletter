"""
Script de test : vérifie quelles URLs de flux RSS fonctionnent
pour les nouvelles sources demandées par l'équipe.

Usage : py test_rss_sources.py
"""

import feedparser
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RiveNewsletterBot/1.0)"}

# Pour chaque source, on teste plusieurs patterns d'URL courants
CANDIDATES = {
    "Conoship": [
        "https://www.conoship.com/news/feed/",
        "https://www.conoship.com/feed/",
        "https://www.conoship.com/category/news/feed/",
    ],
    "Gama Aviation": [
        "https://www.gamaaviation.com/news/feed/",
        "https://www.gamaaviation.com/feed/",
    ],
    "Omni Helicopters International": [
        "https://www.omnihelicoptersinternational.com/news/feed/",
        "https://www.omnihelicoptersinternational.com/feed/",
    ],
    "SMFL Helicopters": [
        "https://smflh.aero/category/press-releases/feed/",
        "https://smflh.aero/feed/",
    ],
    "Aerobuzz": [
        "https://www.aerobuzz.fr/feed/",
    ],
    "Journal de l'Aviation": [
        "https://www.journal-aviation.com/feed",
        "https://www.journal-aviation.com/rss",
        "https://www.journal-aviation.com/feed/",
        "https://www.journal-aviation.com/rss.xml",
    ],
}

def test_url(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"
        feed = feedparser.parse(resp.content)
        if feed.bozo and not feed.entries:
            return False, "Pas un flux RSS/Atom valide"
        if len(feed.entries) == 0:
            return False, "Flux valide mais vide"
        return True, f"OK - {len(feed.entries)} articles, dernier: '{feed.entries[0].title[:60]}'"
    except Exception as e:
        return False, f"Erreur: {e}"

print("=" * 70)
print("TEST DES FLUX RSS - Nouvelles sources")
print("=" * 70)

results = {}
for name, urls in CANDIDATES.items():
    print(f"\n📡 {name}")
    found = False
    for url in urls:
        ok, msg = test_url(url)
        status = "✅" if ok else "❌"
        print(f"   {status} {url}")
        print(f"      → {msg}")
        if ok and not found:
            results[name] = url
            found = True
    if not found:
        results[name] = None

print("\n" + "=" * 70)
print("RÉSUMÉ - URLs à ajouter dans le code")
print("=" * 70)
for name, url in results.items():
    if url:
        print(f"✅ {name}: {url}")
    else:
        print(f"❌ {name}: AUCUN flux RSS trouvé automatiquement - alternative nécessaire")