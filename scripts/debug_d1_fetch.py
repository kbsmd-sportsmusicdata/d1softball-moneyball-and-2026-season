import requests, re, json
try:
    from bs4 import BeautifulSoup
    have_bs4 = True
except Exception:
    have_bs4 = False


def normalize_team_key(team_name):
    cleaned = team_name.lower().strip()
    cleaned = cleaned.replace("st.", "state")
    cleaned = cleaned.replace("st ", "state ")
    cleaned = cleaned.replace("&", " ")
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def slug_candidates(team_name, resolved_slug=None):
    candidates = []
    if resolved_slug:
        candidates.append(resolved_slug)
    team_key = normalize_team_key(team_name)
    candidate_forms = [
        team_key,
        team_key.replace(" ", "-"),
        team_key.replace(" ", ""),
        re.sub(r"[^a-z0-9]+", "-", team_key).strip("-"),
    ]
    for c in candidate_forms:
        c = c.strip().strip("-")
        if c and c not in candidates:
            candidates.append(c)
    return candidates


team_name = "Texas Tech"
season = 2026
candidates = slug_candidates(team_name)
headers = {"User-Agent": "Mozilla/5.0 (compatible; SoftballStatsBot/1.0)"}

for cand in candidates:
    url = f"https://d1softball.com/team/{cand}/{season}/stats/"
    print("---")
    print("URL:", url)
    try:
        r = requests.get(url, headers=headers, timeout=30)
        print("status:", r.status_code, "len:", len(r.text))
    except Exception as e:
        print("request error:", e)
        continue
    html = r.text
    preview = html[:1000].replace('\n', ' ')
    print("preview:", preview[:800])
    if have_bs4:
        soup = BeautifulSoup(html, "html.parser")
        batting = soup.select_one("#batting-stats")
        pitching = soup.select_one("#pitching-stats")
        print("batting:", bool(batting), "pitching:", bool(pitching))
        players = []
        if batting:
            headers_row = [th.get_text(" ", strip=True) for th in batting.select("thead th")]
            if not headers_row:
                fr = batting.select_one("tr")
                if fr:
                    headers_row = [c.get_text(" ", strip=True) for c in fr.select("th,td")]
            for tr in batting.select("tbody tr"):
                cells = [td.get_text(" ", strip=True) for td in tr.select("td")]
                if not cells:
                    continue
                players.append({"headers": headers_row, "cells": cells})
        print("players_parsed:", len(players))
        if players:
            print(json.dumps(players[:5], indent=2))
    else:
        print("bs4 not available in environment; raw HTML preview shown")
