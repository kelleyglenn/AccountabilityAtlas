#!/usr/bin/env python
"""Collect LOC, complexity, and structural metrics across all repos."""

import json
import os
import re
import sys
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

# Resolve project root relative to this script: scripts/metrics/ -> project root
ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT = ROOT / "scripts" / "metrics" / "loc_metrics.json"

REPOS = {
    "top-level": ROOT,
    "api-gateway": ROOT / "AcctAtlas-api-gateway",
    "user-service": ROOT / "AcctAtlas-user-service",
    "video-service": ROOT / "AcctAtlas-video-service",
    "location-service": ROOT / "AcctAtlas-location-service",
    "search-service": ROOT / "AcctAtlas-search-service",
    "moderation-service": ROOT / "AcctAtlas-moderation-service",
    "notification-service": ROOT / "AcctAtlas-notification-service",
    "web-app": ROOT / "AcctAtlas-web-app",
    "integration-tests": ROOT / "AcctAtlas-integration-tests",
}

SKIP_DIRS = {
    ".git", "node_modules", "build", "out", ".gradle", ".next",
    "coverage", "test-results", "playwright-report", ".idea",
    ".vscode", ".worktrees", "__pycache__", "dist", "target",
    ".husky", "seed-data",
}

SKIP_EXTENSIONS = {
    ".jar", ".class", ".png", ".jpg", ".jpeg", ".gif", ".ico",
    ".svg", ".woff", ".woff2", ".ttf", ".eot", ".map", ".lock",
    ".min.js", ".min.css", ".pyc", ".pyo", ".bin", ".dat",
}


def should_skip_dir(dirname):
    return dirname in SKIP_DIRS or dirname.startswith(".")


def should_skip_file(filepath):
    name = filepath.name.lower()
    if name in ("package-lock.json", "gradlew.bat"):
        return True
    return filepath.suffix.lower() in SKIP_EXTENSIONS


# Languages where // and /* */ are comment syntax
C_STYLE_COMMENT_EXTS = {".java", ".ts", ".tsx", ".js", ".jsx", ".css", ".scss", ".gradle"}
# Languages where # is comment syntax
HASH_COMMENT_EXTS = {".py", ".sh", ".bash", ".yml", ".yaml", ".properties", ".tf", ".hcl", ".toml"}
# Languages with no comment counting (content is all "code")
NO_COMMENT_EXTS = {".md", ".json", ".xml", ".html", ".sql"}


def count_lines(filepath):
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        total = len(lines)
        blank = sum(1 for line in lines if line.strip() == "")
        comment = 0
        suffix = filepath.suffix.lower()
        name = filepath.name.lower()

        if name == "dockerfile":
            suffix = ".sh"  # Dockerfile uses # comments

        if suffix in C_STYLE_COMMENT_EXTS:
            in_block = False
            for line in lines:
                stripped = line.strip()
                if in_block:
                    comment += 1
                    if "*/" in stripped:
                        in_block = False
                elif stripped.startswith("//"):
                    comment += 1
                elif stripped.startswith("/*"):
                    comment += 1
                    if "*/" not in stripped:
                        in_block = True
                elif stripped.startswith("* ") or stripped == "*":
                    comment += 1
        elif suffix in HASH_COMMENT_EXTS:
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("#"):
                    comment += 1
        # For NO_COMMENT_EXTS and unknown types, comment stays 0

        code = total - blank - comment
        return {"total": total, "code": max(0, code), "blank": blank, "comment": comment}
    except Exception:
        return {"total": 0, "code": 0, "blank": 0, "comment": 0}


def categorize_file(filepath, repo_name, repo_root):
    rel = filepath.relative_to(repo_root)
    parts = rel.parts
    name = filepath.name.lower()
    suffix = filepath.suffix.lower()

    if ".github" in parts:
        return "ci_cd"

    # Java service categorization
    if repo_name not in ("web-app", "integration-tests", "top-level"):
        if "src" in parts:
            src_idx = parts.index("src")
            if src_idx + 1 < len(parts):
                if parts[src_idx + 1] == "test":
                    return "test"
                if parts[src_idx + 1] == "main":
                    if src_idx + 2 < len(parts):
                        if parts[src_idx + 2] == "resources":
                            if "migration" in parts or "db" in parts:
                                return "migration"
                            return "config"
                        if parts[src_idx + 2] == "java":
                            return "source"
            return "source"
        if name in ("build.gradle", "settings.gradle", "gradlew"):
            return "build"
        if name in ("docker-compose.yml", "dockerfile"):
            return "config"
        if suffix in (".md", ".yaml", ".yml") and ("docs" in parts or name == "readme.md"):
            return "docs"
        if "docker" in parts:
            return "config"
        if "gradle" in parts:
            return "build"
        return "other"

    # Web-app
    if repo_name == "web-app":
        if "__tests__" in parts or name.endswith(".test.ts") or name.endswith(".test.tsx") or name.endswith(".spec.ts"):
            return "test"
        if "src" in parts and suffix in (".ts", ".tsx", ".js", ".jsx", ".css"):
            return "source"
        if suffix in (".md",) or "docs" in parts or name == "readme.md":
            return "docs"
        if name in ("package.json", "tsconfig.json"):
            return "build"
        if "config" in name or name in ("next.config.js", "tailwind.config.ts", "postcss.config.mjs",
                                         "jest.config.js", "playwright.config.js", ".env",
                                         ".env.local", ".env.production"):
            return "config"
        if name == "dockerfile" or name == "docker-compose.yml":
            return "config"
        return "other"

    # Integration tests
    if repo_name == "integration-tests":
        if suffix in (".ts", ".js") and ("tests" in parts or "seeds" in parts or "fixtures" in parts):
            return "test"
        if "config" in name or name in ("playwright.config.ts",):
            return "config"
        if name in ("package.json", "tsconfig.json"):
            return "build"
        if suffix in (".md",) or name == "readme.md":
            return "docs"
        return "other"

    # Top-level
    if repo_name == "top-level":
        if "docs" in parts:
            return "docs"
        if "scripts" in parts:
            return "scripts"
        if "infra" in parts:
            return "infra"
        if name in ("build.gradle", "settings.gradle"):
            return "build"
        if name in ("docker-compose.yml", "sonar-project.properties"):
            return "config"
        if suffix == ".md":
            return "docs"
        if "gradle" in parts:
            return "build"
        return "other"

    return "other"


def get_language(filepath):
    suffix = filepath.suffix.lower()
    name = filepath.name.lower()
    lang_map = {
        ".java": "Java",
        ".ts": "TypeScript",
        ".tsx": "TypeScript (JSX)",
        ".js": "JavaScript",
        ".jsx": "JavaScript (JSX)",
        ".css": "CSS",
        ".scss": "SCSS",
        ".html": "HTML",
        ".sql": "SQL",
        ".yml": "YAML",
        ".yaml": "YAML",
        ".json": "JSON",
        ".xml": "XML",
        ".properties": "Properties",
        ".md": "Markdown",
        ".sh": "Shell",
        ".bash": "Shell",
        ".tf": "Terraform/OpenTofu",
        ".hcl": "HCL",
        ".gradle": "Gradle (Groovy)",
        ".toml": "TOML",
        ".py": "Python",
    }
    if name == "dockerfile":
        return "Dockerfile"
    if name == "gradlew":
        return "Shell"
    return lang_map.get(suffix, "Other")


def count_complexity(filepath):
    complexity = {
        "if_statements": 0, "else_if": 0, "else_blocks": 0,
        "switch_cases": 0, "catch_blocks": 0, "ternary": 0,
        "loops": 0, "logical_operators": 0,
    }
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        suffix = filepath.suffix.lower()
        if suffix in (".java", ".ts", ".tsx", ".js", ".jsx"):
            complexity["if_statements"] = len(re.findall(r"\bif\s*\(", content))
            complexity["else_if"] = len(re.findall(r"\belse\s+if\s*\(", content))
            complexity["else_blocks"] = len(re.findall(r"\}\s*else\s*\{", content))
            complexity["switch_cases"] = len(re.findall(r"\bcase\s+", content))
            complexity["catch_blocks"] = len(re.findall(r"\bcatch\s*\(", content))
            complexity["ternary"] = content.count(" ? ") + content.count("\t? ")
            complexity["loops"] = len(re.findall(r"\b(for|while)\s*\(", content))
            complexity["logical_operators"] = len(re.findall(r"&&|\|\|", content))
    except Exception:
        pass
    return complexity


def count_java_annotations(filepath):
    annotations = {}
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        for ann in ["@Entity", "@Repository", "@Service", "@RestController",
                     "@Controller", "@Component", "@Configuration", "@Bean",
                     "@EventListener", "@Scheduled"]:
            count = len(re.findall(re.escape(ann) + r"(?:\b|$)", content))
            if count > 0:
                annotations[ann] = count
    except Exception:
        pass
    return annotations


def count_react_components(filepath):
    count = 0
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        count += len(re.findall(r"export\s+(default\s+)?function\s+\w+", content))
        count += len(re.findall(r"export\s+const\s+\w+\s*[:=]\s*(React\.)?FC", content))
        if filepath.name in ("page.tsx", "page.ts", "layout.tsx", "layout.ts"):
            if "export default" in content:
                count = max(count, 1)
    except Exception:
        pass
    return count


def count_nextjs_routes(repo_root):
    pages = 0
    api_routes = 0
    app_dir = repo_root / "src" / "app"
    if app_dir.exists():
        for f in app_dir.rglob("page.tsx"):
            pages += 1
        for f in app_dir.rglob("page.ts"):
            pages += 1
        for f in app_dir.rglob("route.ts"):
            api_routes += 1
        for f in app_dir.rglob("route.tsx"):
            api_routes += 1
    return {"pages": pages, "api_routes": api_routes}


def parse_dependencies(repo_root):
    deps = {"compile": 0, "test": 0, "total": 0}
    build_gradle = repo_root / "build.gradle"
    if build_gradle.exists():
        try:
            with open(build_gradle, "r", encoding="utf-8") as f:
                content = f.read()
            compile_deps = len(re.findall(r"\b(implementation|api|compileOnly)\s+['\"]", content))
            test_deps = len(re.findall(r"\b(testImplementation|testCompileOnly|testRuntimeOnly)\s+['\"]", content))
            deps["compile"] = compile_deps
            deps["test"] = test_deps
            deps["total"] = compile_deps + test_deps
        except Exception:
            pass
    pkg_json = repo_root / "package.json"
    if pkg_json.exists():
        try:
            with open(pkg_json, "r", encoding="utf-8") as f:
                pkg = json.load(f)
            compile_deps = len(pkg.get("dependencies", {}))
            test_deps = len(pkg.get("devDependencies", {}))
            deps["compile"] = compile_deps
            deps["test"] = test_deps
            deps["total"] = compile_deps + test_deps
        except Exception:
            pass
    return deps


def analyze_repo(repo_name, repo_root):
    print(f"  Analyzing {repo_name}...")
    if not repo_root.exists():
        return None

    result = {
        "name": repo_name,
        "loc": {},
        "languages": {},
        "complexity": {
            "if_statements": 0, "else_if": 0, "else_blocks": 0,
            "switch_cases": 0, "catch_blocks": 0, "ternary": 0,
            "loops": 0, "logical_operators": 0,
        },
        "annotations": {},
        "react_components": 0,
        "dependencies": parse_dependencies(repo_root),
        "file_count": 0,
        "total_loc": {"total": 0, "code": 0, "blank": 0, "comment": 0},
    }

    loc_cats = defaultdict(lambda: {"total": 0, "code": 0, "blank": 0, "comment": 0, "files": 0})
    lang_stats = defaultdict(lambda: {"total": 0, "code": 0, "files": 0})
    ann_counts = defaultdict(int)

    skip_subdirs = set()
    if repo_name == "top-level":
        skip_subdirs = {p.name for name, p in REPOS.items() if name != "top-level"}

    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d) and d not in skip_subdirs]

        for filename in filenames:
            filepath = Path(dirpath) / filename
            if should_skip_file(filepath):
                continue

            category = categorize_file(filepath, repo_name, repo_root)
            language = get_language(filepath)
            lines = count_lines(filepath)

            loc_cats[category]["total"] += lines["total"]
            loc_cats[category]["code"] += lines["code"]
            loc_cats[category]["blank"] += lines["blank"]
            loc_cats[category]["comment"] += lines["comment"]
            loc_cats[category]["files"] += 1

            lang_stats[language]["total"] += lines["total"]
            lang_stats[language]["code"] += lines["code"]
            lang_stats[language]["files"] += 1

            result["total_loc"]["total"] += lines["total"]
            result["total_loc"]["code"] += lines["code"]
            result["total_loc"]["blank"] += lines["blank"]
            result["total_loc"]["comment"] += lines["comment"]
            result["file_count"] += 1

            if category == "source":
                cx = count_complexity(filepath)
                for key, val in cx.items():
                    result["complexity"][key] += val
                if filepath.suffix == ".java":
                    anns = count_java_annotations(filepath)
                    for ann, count in anns.items():
                        ann_counts[ann] += count
                if filepath.suffix in (".tsx", ".jsx"):
                    result["react_components"] += count_react_components(filepath)

            if category == "test":
                cx = count_complexity(filepath)
                for key, val in cx.items():
                    result["complexity"][key] += val

    if repo_name == "web-app":
        result["nextjs_routes"] = count_nextjs_routes(repo_root)

    result["loc"] = {k: dict(v) for k, v in loc_cats.items()}
    result["languages"] = {k: dict(v) for k, v in lang_stats.items()}
    result["annotations"] = dict(ann_counts)

    return result


def compute_estimated_cc(cx):
    return (1
            + cx.get("if_statements", 0)
            + cx.get("else_if", 0)
            + cx.get("switch_cases", 0)
            + cx.get("catch_blocks", 0)
            + cx.get("loops", 0)
            + cx.get("logical_operators", 0))


def main():
    print("Collecting LOC and structural metrics...")
    all_metrics = {"repos": {}, "overall": {}}

    for name, path in REPOS.items():
        result = analyze_repo(name, path)
        if result:
            result["estimated_cyclomatic_complexity"] = compute_estimated_cc(result["complexity"])
            all_metrics["repos"][name] = result

    # Overall
    overall = {
        "total_loc": {"total": 0, "code": 0, "blank": 0, "comment": 0},
        "file_count": 0,
        "complexity": {
            "if_statements": 0, "else_if": 0, "else_blocks": 0,
            "switch_cases": 0, "catch_blocks": 0, "ternary": 0,
            "loops": 0, "logical_operators": 0,
        },
        "languages": {},
        "loc_by_category": {},
    }

    lang_agg = defaultdict(lambda: {"total": 0, "code": 0, "files": 0})
    cat_agg = defaultdict(lambda: {"total": 0, "code": 0, "blank": 0, "comment": 0, "files": 0})

    for name, repo in all_metrics["repos"].items():
        overall["total_loc"]["total"] += repo["total_loc"]["total"]
        overall["total_loc"]["code"] += repo["total_loc"]["code"]
        overall["total_loc"]["blank"] += repo["total_loc"]["blank"]
        overall["total_loc"]["comment"] += repo["total_loc"]["comment"]
        overall["file_count"] += repo["file_count"]
        for key in overall["complexity"]:
            overall["complexity"][key] += repo["complexity"].get(key, 0)
        for lang, data in repo["languages"].items():
            for k in ("total", "code", "files"):
                lang_agg[lang][k] += data[k]
        for cat, data in repo["loc"].items():
            for k in ("total", "code", "blank", "comment", "files"):
                cat_agg[cat][k] += data.get(k, 0)

    overall["estimated_cyclomatic_complexity"] = compute_estimated_cc(overall["complexity"])
    overall["languages"] = {k: dict(v) for k, v in lang_agg.items()}
    overall["loc_by_category"] = {k: dict(v) for k, v in cat_agg.items()}
    all_metrics["overall"] = overall

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, indent=2, default=str)

    print(f"\nMetrics written to {OUTPUT}")
    print(f"\n{'='*50}")
    print(f"Total files: {overall['file_count']}")
    print(f"Total lines: {overall['total_loc']['total']:,}")
    print(f"Code lines:  {overall['total_loc']['code']:,}")
    print(f"Blank lines: {overall['total_loc']['blank']:,}")
    print(f"Comments:    {overall['total_loc']['comment']:,}")
    print(f"Est. CC:     {overall['estimated_cyclomatic_complexity']:,}")
    print(f"{'='*50}")

    # Per-repo summary
    print(f"\n{'Repo':<25} {'Files':>6} {'Total':>8} {'Code':>8}")
    print("-" * 50)
    for name, repo in all_metrics["repos"].items():
        print(f"{name:<25} {repo['file_count']:>6} {repo['total_loc']['total']:>8,} {repo['total_loc']['code']:>8,}")


if __name__ == "__main__":
    main()
