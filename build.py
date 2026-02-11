#!/usr/bin/env python3
"""
Build script: renders all markdown posts into a static site.

Reads all .md files from content/, generates:
  _site/
    index.html                      (homepage with post listing)
    <slug>/index.html               (each post)
    robots.txt
    sitemap.xml
    CNAME

Usage:
  python build.py                                  # defaults
  python build.py -c content/ -o _site/            # explicit paths
"""

import glob
import math
import os
import re
import sys
from datetime import datetime

try:
    import markdown
except ImportError:
    print("Missing dependency. Install with: pip install markdown")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def parse_frontmatter(text):
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not match:
        return None, text

    meta = {}
    for line in match.group(1).strip().splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()

    return meta, match.group(2)


def estimate_read_time(text):
    words = len(text.split())
    return max(1, math.ceil(words / 250))


def get_snippet(description, max_len=100):
    """Get a short snippet from description."""
    if len(description) <= max_len:
        return description
    return description[:max_len].rsplit(' ', 1)[0] + "..."


def build_post_nav(prev_post, next_post):
    """Generate navigation HTML for prev/next posts."""
    nav_items = []

    if prev_post:
        snippet = get_snippet(prev_post["description"])
        nav_items.append(
            f'      <div class="post-nav-item prev">\n'
            f'        <div class="post-nav-label">Previous</div>\n'
            f'        <a href="/{prev_post["slug"]}/" class="post-nav-title">{prev_post["title"]}</a>\n'
            f'        <div class="post-nav-snippet">{snippet}</div>\n'
            f'      </div>'
        )
    else:
        nav_items.append('      <div class="post-nav-item prev"></div>')

    if next_post:
        snippet = get_snippet(next_post["description"])
        nav_items.append(
            f'      <div class="post-nav-item next">\n'
            f'        <div class="post-nav-label">Next</div>\n'
            f'        <a href="/{next_post["slug"]}/" class="post-nav-title">{next_post["title"]}</a>\n'
            f'        <div class="post-nav-snippet">{snippet}</div>\n'
            f'      </div>'
        )
    else:
        nav_items.append('      <div class="post-nav-item next"></div>')

    return "\n".join(nav_items)


def build_post(md_path, template, out_dir, all_posts, post_index, featured_post):
    with open(md_path, "r") as f:
        raw = f.read()

    meta, body_md = parse_frontmatter(raw)

    required = ["title", "slug", "description", "date", "domain"]
    for key in required:
        if key not in meta:
            print(f"Error: {md_path} missing front matter field: {key}")
            sys.exit(1)

    body_html = markdown.markdown(body_md, extensions=["extra", "smarty"])
    read_time = str(estimate_read_time(body_md))

    # Determine prev/next posts
    prev_post = all_posts[post_index - 1] if post_index > 0 else None
    next_post = all_posts[post_index + 1] if post_index < len(all_posts) - 1 else None

    post_nav = build_post_nav(prev_post, next_post)

    html = template
    html = html.replace("{{TITLE}}", meta["title"])
    html = html.replace("{{META_DESCRIPTION}}", meta["description"])
    html = html.replace("{{DOMAIN}}", meta["domain"])
    html = html.replace("{{SLUG}}", meta["slug"])
    html = html.replace("{{DATE}}", meta["date"])
    html = html.replace("{{READ_TIME}}", read_time)
    html = html.replace("{{CONTENT}}", body_html)
    html = html.replace("{{POST_NAV}}", post_nav)
    html = html.replace("{{FEATURED_SLUG}}", featured_post["slug"])
    html = html.replace("{{FEATURED_TITLE}}", featured_post["title"])
    html = html.replace("{{FEATURED_SNIPPET}}", get_snippet(featured_post["description"]))

    post_dir = os.path.join(out_dir, meta["slug"])
    os.makedirs(post_dir, exist_ok=True)
    with open(os.path.join(post_dir, "index.html"), "w") as f:
        f.write(html)

    print(f"  Post: /{meta['slug']}/")
    return meta


def build_homepage(posts, home_template, domain, out_dir):
    items = []
    for p in posts:
        items.append(
            f'      <li>\n'
            f'        <a href="/{p["slug"]}/">{p["title"]}</a>\n'
            f'        <div class="post-date">{p["date"]}</div>\n'
            f'        <div class="post-desc">{p["description"]}</div>\n'
            f'      </li>'
        )

    html = home_template
    html = html.replace("{{DOMAIN}}", domain)
    html = html.replace("{{POST_LIST}}", "\n".join(items))

    with open(os.path.join(out_dir, "index.html"), "w") as f:
        f.write(html)

    print("  Home: /")


def build_robots(domain, out_dir):
    txt = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: https://{domain}/sitemap.xml\n"
    )
    with open(os.path.join(out_dir, "robots.txt"), "w") as f:
        f.write(txt)
    print("  robots.txt")


def build_sitemap(posts, domain, out_dir):
    today = datetime.now().strftime("%Y-%m-%d")
    urls = [f"  <url>\n    <loc>https://{domain}/</loc>\n    <lastmod>{today}</lastmod>\n  </url>"]
    for p in posts:
        urls.append(
            f"  <url>\n"
            f"    <loc>https://{domain}/{p['slug']}/</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"  </url>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls) + "\n"
        '</urlset>\n'
    )
    with open(os.path.join(out_dir, "sitemap.xml"), "w") as f:
        f.write(xml)
    print("  sitemap.xml")


def build_cname(domain, out_dir):
    with open(os.path.join(out_dir, "CNAME"), "w") as f:
        f.write(domain + "\n")
    print("  CNAME")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build static site from markdown")
    parser.add_argument("-c", "--content", default="content", help="Content directory")
    parser.add_argument("-o", "--out", default="_site", help="Output directory")
    args = parser.parse_args()

    post_template_path = os.path.join(SCRIPT_DIR, "index.html")
    home_template_path = os.path.join(SCRIPT_DIR, "home.html")

    with open(post_template_path, "r") as f:
        post_template = f.read()
    with open(home_template_path, "r") as f:
        home_template = f.read()

    md_files = sorted(glob.glob(os.path.join(args.content, "*.md")))
    if not md_files:
        print(f"No .md files found in {args.content}/")
        sys.exit(1)

    os.makedirs(args.out, exist_ok=True)

    print(f"Building {len(md_files)} post(s)...")

    # First pass: parse all posts to get metadata
    posts = []
    for md in md_files:
        with open(md, "r") as f:
            raw = f.read()
        meta, _ = parse_frontmatter(raw)
        meta["_path"] = md
        posts.append(meta)

    domain = posts[0]["domain"] if posts else None

    # Find featured post (first one with featured: true, or fallback to first post)
    featured_post = next(
        (p for p in posts if p.get("featured", "").lower() == "true"),
        posts[0]
    )

    # Second pass: build each post with navigation context
    for i, md in enumerate(md_files):
        build_post(md, post_template, args.out, posts, i, featured_post)

    build_homepage(posts, home_template, domain, args.out)
    build_robots(domain, args.out)
    build_sitemap(posts, domain, args.out)
    build_cname(domain, args.out)
    print("Done.")


if __name__ == "__main__":
    main()
