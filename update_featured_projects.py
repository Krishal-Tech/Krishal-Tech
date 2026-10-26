#!/usr/bin/env python3
"""Update the featured-project section in README.md using GitHub repository metrics."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OWNER = os.environ.get("GITHUB_OWNER", "Krishal-Tech")
README = Path(os.environ.get("README_PATH", "README.md"))
TOKEN = os.environ.get("GH_TRAFFIC_TOKEN", "")
START = "<!-- FEATURED_PROJECTS:START -->"
END = "<!-- FEATURED_PROJECTS:END -->"
API = "https://api.github.com"


def api_get(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "featured-projects-readme-updater",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def safe_text(value: str) -> str:
    return (value or "No description provided.").replace("\r", " ").replace("\n", " ").replace("|", "\\|").strip()


def get_views(repo_full_name: str):
    """Return (view count, True) if traffic is readable, otherwise (0, False)."""
    url = f"{API}/repos/{repo_full_name}/traffic/views"
    try:
        data = api_get(url)
        return int(data.get("count", 0)), True
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        return 0, False


def main():
    if not README.exists():
        raise SystemExit(f"README not found: {README}")

    repos_url = f"{API}/users/{urllib.parse.quote(OWNER)}/repos?per_page=100&type=owner&sort=updated"
    repos = api_get(repos_url)
    if not isinstance(repos, list):
        raise SystemExit("GitHub did not return a repository list.")

    # Exclude forks, archived repos, disabled repos, and the special profile README repository.
    repos = [
        r for r in repos
        if not r.get("fork")
        and not r.get("archived")
        and not r.get("disabled")
        and r.get("name", "").lower() != OWNER.lower()
    ]

    if not repos:
        section = "_No eligible repositories found yet._"
    else:
        traffic_results = []
        traffic_available = 0
        for repo in repos:
            views, available = get_views(repo["full_name"])
            traffic_available += int(available)
            traffic_results.append({**repo, "recent_views": views})

        # If none of the traffic endpoints are readable, fall back to star-based ranking.
        if traffic_available == 0:
            ranked = sorted(traffic_results, key=lambda r: (r.get("stargazers_count", 0), r.get("updated_at", "")), reverse=True)
            ranking_note = "Traffic data was unavailable to the workflow, so this list is ranked by stars."
        else:
            # Combine ordinal ranks so stars and 14-day views contribute equally without
            # adding incomparable raw numbers together. Lower rank numbers are better.
            star_order = sorted(traffic_results, key=lambda r: (r.get("stargazers_count", 0), r.get("updated_at", "")), reverse=True)
            view_order = sorted(traffic_results, key=lambda r: (r.get("recent_views", 0), r.get("stargazers_count", 0)), reverse=True)
            star_rank = {r["full_name"]: i for i, r in enumerate(star_order)}
            view_rank = {r["full_name"]: i for i, r in enumerate(view_order)}
            for r in traffic_results:
                r["combined_score"] = star_rank[r["full_name"]] + view_rank[r["full_name"]]
            ranked = sorted(
                traffic_results,
                key=lambda r: (r["combined_score"], -r.get("stargazers_count", 0), -r.get("recent_views", 0)),
            )
            ranking_note = "Ranked by combined star rank and recent-view rank (last 14 days)."

        rows = [
            "| Repository | Description | Stars | Views (14 days) | Language |",
            "|---|---|---:|---:|---|",
        ]
        for repo in ranked[:3]:
            name = repo["name"]
            url = repo.get("html_url", f"https://github.com/{repo['full_name']}")
            description = safe_text(repo.get("description") or "No description provided.")
            language = safe_text(repo.get("language") or "—")
            stars = int(repo.get("stargazers_count", 0))
            views = int(repo.get("recent_views", 0))
            rows.append(f"| [{name}]({url}) | {description} | ⭐ {stars} | {views} | {language} |")
        rows.extend(["", f"<sub>{ranking_note} Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.</sub>"])
        section = "\n".join(rows)

    content = README.read_text(encoding="utf-8")
    if START not in content or END not in content:
        raise SystemExit("Could not find featured-project markers in README.md.")
    before, rest = content.split(START, 1)
    _, after = rest.split(END, 1)
    updated = f"{before}{START}\n{section}\n{END}{after}"
    if updated != content:
        README.write_text(updated, encoding="utf-8")
        print("Updated featured projects in README.md")
    else:
        print("Featured-project section is already up to date")


if __name__ == "__main__":
    main()
