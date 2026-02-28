"""Collect git and GitHub metrics across all AccountabilityAtlas repos.

Gathers commit counts, lines added/removed, Claude co-authorship stats,
merged PR counts, and issue counts for each repository.

Usage:
    python scripts/metrics/collect_metrics.py

Output:
    scripts/metrics/git_metrics.json
"""

import subprocess
import json
import sys
import os
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")

# Resolve project root relative to this script: scripts/metrics/ -> project root
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPOS = [
    (BASE, "kelleyglenn/AccountabilityAtlas"),
    (os.path.join(BASE, "AcctAtlas-api-gateway"), "kelleyglenn/AcctAtlas-api-gateway"),
    (os.path.join(BASE, "AcctAtlas-user-service"), "kelleyglenn/AcctAtlas-user-service"),
    (os.path.join(BASE, "AcctAtlas-video-service"), "kelleyglenn/AcctAtlas-video-service"),
    (os.path.join(BASE, "AcctAtlas-location-service"), "kelleyglenn/AcctAtlas-location-service"),
    (os.path.join(BASE, "AcctAtlas-search-service"), "kelleyglenn/AcctAtlas-search-service"),
    (os.path.join(BASE, "AcctAtlas-moderation-service"), "kelleyglenn/AcctAtlas-moderation-service"),
    (os.path.join(BASE, "AcctAtlas-notification-service"), "kelleyglenn/AcctAtlas-notification-service"),
    (os.path.join(BASE, "AcctAtlas-web-app"), "kelleyglenn/AcctAtlas-web-app"),
    (os.path.join(BASE, "AcctAtlas-integration-tests"), "kelleyglenn/AcctAtlas-integration-tests"),
]

OUTPUT_FILE = os.path.join(BASE, "scripts", "metrics", "git_metrics.json")


def run(cmd, shell=True):
    try:
        result = subprocess.run(
            cmd, shell=shell, capture_output=True, text=True, timeout=120, encoding="utf-8"
        )
        if result.returncode != 0:
            print(f"  WARNING: command failed (rc={result.returncode}): {cmd}", file=sys.stderr)
            print(f"  stderr: {result.stderr.strip()}", file=sys.stderr)
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"  WARNING: command timed out: {cmd}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  WARNING: command error: {cmd} -> {e}", file=sys.stderr)
        return None


def collect_git_metrics(repo_path):
    print(f"Collecting git metrics for {repo_path} ...")
    metrics = {}

    out = run(f'git -C "{repo_path}" rev-list --count HEAD')
    metrics["total_commits"] = int(out) if out else 0

    out = run(f'git -C "{repo_path}" log --reverse --format=%aI')
    if out:
        metrics["first_commit_date"] = out.split("\n")[0].strip()
    else:
        metrics["first_commit_date"] = None

    out = run(f'git -C "{repo_path}" log -1 --format=%aI')
    metrics["latest_commit_date"] = out if out else None

    out = run(f'git -C "{repo_path}" log --numstat --format=""')
    la, lr = 0, 0
    if out:
        for line in out.split("\n"):
            parts = line.split("\t")
            if len(parts) >= 2:
                try:
                    la += int(parts[0])
                    lr += int(parts[1])
                except ValueError:
                    pass
    metrics["lines_added"] = la
    metrics["lines_removed"] = lr

    out = run(f'git -C "{repo_path}" log --grep="Co-Authored-By: Claude" --oneline')
    if out:
        metrics["claude_coauthored_commits"] = len(out.strip().split("\n"))
    else:
        metrics["claude_coauthored_commits"] = 0

    return metrics


def collect_github_metrics(gh_repo):
    print(f"Collecting GitHub metrics for {gh_repo} ...")
    metrics = {}

    out = run(f"gh pr list -R {gh_repo} --state merged --limit 999 --json number")
    if out:
        try:
            metrics["merged_pr_count"] = len(json.loads(out))
        except json.JSONDecodeError:
            metrics["merged_pr_count"] = 0
    else:
        metrics["merged_pr_count"] = 0

    out = run(f"gh issue list -R {gh_repo} --state all --limit 999 --json number,state")
    if out:
        try:
            issues = json.loads(out)
            metrics["total_issues"] = len(issues)
            metrics["open_issues"] = sum(1 for i in issues if i.get("state") == "OPEN")
            metrics["closed_issues"] = sum(1 for i in issues if i.get("state") == "CLOSED")
        except json.JSONDecodeError:
            metrics["total_issues"] = 0
            metrics["open_issues"] = 0
            metrics["closed_issues"] = 0
    else:
        metrics["total_issues"] = 0
        metrics["open_issues"] = 0
        metrics["closed_issues"] = 0

    return metrics


def main():
    all_metrics = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "repos": {},
        "totals": {},
    }

    for repo_path, gh_repo in REPOS:
        repo_name = os.path.basename(repo_path)
        sep = "=" * 60
        print(f"\n{sep}")
        print(f"Processing: {repo_name}")
        print(sep)

        git_data = collect_git_metrics(repo_path)
        gh_data = collect_github_metrics(gh_repo)

        all_metrics["repos"][repo_name] = {
            "path": repo_path,
            "github_repo": gh_repo,
            "git": git_data,
            "github": gh_data,
        }

    totals = {
        "total_commits": 0,
        "total_lines_added": 0,
        "total_lines_removed": 0,
        "total_claude_coauthored_commits": 0,
        "total_merged_prs": 0,
        "total_issues": 0,
        "total_open_issues": 0,
        "total_closed_issues": 0,
        "earliest_commit_date": None,
        "latest_commit_date": None,
        "repo_count": len(REPOS),
    }

    for repo_name, data in all_metrics["repos"].items():
        g = data["git"]
        h = data["github"]
        totals["total_commits"] += g.get("total_commits", 0)
        totals["total_lines_added"] += g.get("lines_added", 0)
        totals["total_lines_removed"] += g.get("lines_removed", 0)
        totals["total_claude_coauthored_commits"] += g.get("claude_coauthored_commits", 0)
        totals["total_merged_prs"] += h.get("merged_pr_count", 0)
        totals["total_issues"] += h.get("total_issues", 0)
        totals["total_open_issues"] += h.get("open_issues", 0)
        totals["total_closed_issues"] += h.get("closed_issues", 0)

        first = g.get("first_commit_date")
        if first:
            if totals["earliest_commit_date"] is None or first < totals["earliest_commit_date"]:
                totals["earliest_commit_date"] = first

        latest = g.get("latest_commit_date")
        if latest:
            if totals["latest_commit_date"] is None or latest > totals["latest_commit_date"]:
                totals["latest_commit_date"] = latest

    totals["total_net_lines"] = totals["total_lines_added"] - totals["total_lines_removed"]
    all_metrics["totals"] = totals

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, indent=2, ensure_ascii=False)

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"Results written to {OUTPUT_FILE}")
    print(sep)
    t = totals
    print(f"\nSUMMARY:")
    print(f"  Repos:              {t['repo_count']}")
    print(f"  Total commits:      {t['total_commits']}")
    print(f"  Lines added:        {t['total_lines_added']:,}")
    print(f"  Lines removed:      {t['total_lines_removed']:,}")
    print(f"  Net lines:          {t['total_net_lines']:,}")
    print(f"  Claude co-authored: {t['total_claude_coauthored_commits']}")
    print(f"  Merged PRs:         {t['total_merged_prs']}")
    print(f"  Total issues:       {t['total_issues']} (open: {t['total_open_issues']}, closed: {t['total_closed_issues']})")
    print(f"  Earliest commit:    {t['earliest_commit_date']}")
    print(f"  Latest commit:      {t['latest_commit_date']}")


if __name__ == "__main__":
    main()
