#!/usr/bin/env python3
import json, os, sys, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

OWNER, REPO = os.environ["GITHUB_REPOSITORY"].split("/", 1)
README = Path("README.md")
API = "https://api.github.com"
TOKEN = os.getenv("GITHUB_TOKEN")
TRAFFIC_TOKEN = os.getenv("GH_TRAFFIC_TOKEN")
FS, FE = "<!-- FEATURED_PROJECTS:START -->", "<!-- FEATURED_PROJECTS:END -->"
AS, AE = "<!-- GITHUB_ANALYTICS:START -->", "<!-- GITHUB_ANALYTICS:END -->"

def get(path, token=TOKEN):
    headers = {"Accept":"application/vnd.github+json",
               "X-GitHub-Api-Version":"2022-11-28",
               "User-Agent":"Krishal-Profile-Analytics"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as res:
        return json.loads(res.read().decode())

def replace_block(text, start, end, body):
    if start not in text or end not in text:
        raise RuntimeError(f"Missing README markers: {start} / {end}")
    left, rest = text.split(start, 1)
    _, right = rest.split(end, 1)
    return left + start + "\n" + body.rstrip() + "\n" + end + right

def repositories():
    found, page = [], 1
    while True:
        batch = get(f"/users/{OWNER}/repos?type=owner&per_page=100&page={page}")
        if not batch: break
        found.extend(batch)
        if len(batch) < 100: break
        page += 1
    return [r for r in found if not r["fork"] and not r["archived"]
            and not r["disabled"] and r["name"] != REPO]

def language_totals(repos):
    totals = {}
    for repo in repos:
        try:
            for lang, size in get(f"/repos/{OWNER}/{repo['name']}/languages").items():
                totals[lang] = totals.get(lang, 0) + size
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            pass
    return sorted(totals.items(), key=lambda x: x[1], reverse=True)

def views(name):
    if not TRAFFIC_TOKEN: return None
    try:
        return int(get(f"/repos/{OWNER}/{name}/traffic/views", TRAFFIC_TOKEN).get("count", 0))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        return None

def featured(repos):
    ranked, traffic_ok = [], False
    for r in repos:
        v = views(r["name"])
        if v is not None: traffic_ok = True
        ranked.append((r, v))
    if traffic_ok:
        ranked.sort(key=lambda x: (x[1] if x[1] is not None else -1,
                                   x[0].get("stargazers_count", 0)), reverse=True)
    else:
        ranked.sort(key=lambda x: x[0].get("stargazers_count", 0), reverse=True)
    rows = ["| Repository | Description | Stars | Views (14 days) | Language |",
            "|---|---|---:|---:|---|"]
    for r, v in ranked[:3]:
        name = r["name"]
        desc = (r.get("description") or "No description provided.").replace("|", "\\|")
        rows.append(f"| [{name}](https://github.com/{OWNER}/{name}) | {desc} | "
                    f"⭐ {r.get('stargazers_count', 0)} | {v if v is not None else '—'} | "
                    f"{r.get('language') or '—'} |")
    if not ranked: rows.append("| No public projects found | — | — | — | — |")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    note = ("Traffic data available for at least some repositories." if traffic_ok
            else "Traffic data unavailable; ranked by stars.")
    rows += ["", f"<sub>{note} Last refreshed: {stamp}.</sub>"]
    return "\n".join(rows)

def analytics(repos, langs):
    stars = sum(r.get("stargazers_count", 0) for r in repos)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out = ["<div align=\"center\">", "",
           "| ⭐ Total Stars | 📁 Public Repositories | 🧠 Languages Detected |",
           "|:---:|:---:|:---:|",
           f"| **{stars}** | **{len(repos)}** | **{len(langs)}** |",
           "", "**Most Used Programming Languages**", ""]
    if langs:
        out += ["| Language | Relative code volume |", "|---|---|"]
        maximum = langs[0][1] or 1
        for name, size in langs[:8]:
            n = max(1, round(size / maximum * 10))
            out.append(f"| **{name}** | `{'▰' * n}{'▱' * (10-n)}` |")
    else:
        out.append("_No public language data returned by GitHub._")
    out += ["", f"<sub>Generated from GitHub's public repository API. Last refreshed: {stamp}.</sub>",
            "", "</div>"]
    return "\n".join(out)

def main():
    if not README.exists(): raise RuntimeError("README.md not found at repository root.")
    text = README.read_text(encoding="utf-8")
    repos = repositories()
    langs = language_totals(repos)
    text = replace_block(text, FS, FE, featured(repos))
    text = replace_block(text, AS, AE, analytics(repos, langs))
    README.write_text(text, encoding="utf-8")
    print(f"Updated: {len(repos)} public repositories; "
          f"{sum(r.get('stargazers_count', 0) for r in repos)} stars; {len(langs)} languages.")

if __name__ == "__main__":
    try: main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
