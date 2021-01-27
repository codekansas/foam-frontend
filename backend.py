#!/usr/bin/env python

__all__ = ["Backend"]

import itertools
import logging
import os
import pickle
import re
from pathlib import Path
from typing import List, Optional

import markdown
import markdown.extensions.codehilite
import markdown.extensions.fenced_code

logger = logging.getLogger(__name__)


class Backlinks:
    """Utility class for efficiently managing backlinks."""

    def __init__(self, cache_dir: Path, fpaths: List[Path]) -> None:
        self.ignore_cached = bool(os.environ.get("IGNORE_CACHED", False))

        self.cache_dir = cache_dir
        self.cache_path = cache_dir / "backlinks.pkl"
        self.fpaths = fpaths

        self.backlinks = {}
        self.mtimes = {}
        self.load()

    def load(self) -> None:
        if self.cache_path.exists():
            with open(self.cache_path, "rb") as f:
                pkl_data = pickle.load(f)
                self.backlinks = pkl_data["backlinks"]
                self.mtimes = pkl_data["mtimes"]

        # Updates backlinks cache with new mod times.
        for fpath in self.fpaths:
            k = fpath.stem
            if self.ignore_cached or fpath.stat().st_mtime > self.mtimes.get(k, 0):
                self.mtimes[k] = fpath.stat().st_mtime
                self.add_backlinks(fpath)

        self.save()

    def add_backlinks(self, fpath: Path) -> None:
        with open(fpath, "r") as f:
            for match in re.finditer(r"\[\[(.+?)\]\]", f.read()):
                link_to = match.group(1)
                if link_to not in self.backlinks:
                    self.backlinks[link_to] = {fpath.stem}
                else:
                    self.backlinks[link_to].add(fpath.stem)

    def save(self) -> None:
        with open(self.cache_path, "wb") as f:
            pkl_data = {"backlinks": self.backlinks, "mtimes": self.mtimes}
            pickle.dump(pkl_data, f)

    def __getitem__(self, fpath: str) -> List[str]:
        return list(sorted(self.backlinks.get(fpath, {})))


class Backend:
    def __init__(self, root_path: str) -> None:
        self.ignore_cached = bool(os.environ.get("IGNORE_CACHED", False))

        self.root_path = Path(root_path)
        self.cache_dir = self.root_path / ".cache"
        self.cache_dir.mkdir(exist_ok=True)

        if "NOTES_ROOT" not in os.environ:
            raise ValueError("Set NOTES_ROOT environment variable "
                             "to point at your notes directory")
        self.notes_root = Path(os.environ["NOTES_ROOT"])

        self.md_ctx = markdown.Markdown(
            extensions=[
                "tables",
                "fenced_code",
                "codehilite",
                "mdx_math",
                "markdown_checklists.extension",
            ],
            tab_length=2,
        )

        fpaths = list(self.notes_root.glob("*.md"))
        logger.info("Building directory of %d files", len(fpaths))
        self._titles = {fpath.stem: self.read_title(fpath) for fpath in fpaths}
        self._backlinks = Backlinks(self.cache_dir, fpaths)

    def render_link(self, href: str, value: str) -> str:
        return f"<a href={href}>{value}</a>"

    def update_links(self, match: re.Match) -> str:
        fname = match.group(1)
        return self.render_link(fname, self.title(fname))

    def read_title(self, fpath: Path) -> str:
        with open(fpath, "r") as f:
            title = f.readline()
        if not title:
            return self.default_title(fpath.stem)
        return title[2:].strip()

    def default_title(self, fname: str) -> str:
        return fname.replace("-", " ").replace("_", "_").capitalize()

    def cached_file(self, fname: str) -> Path:
        return self.cache_dir / f"{fname}.html"

    def file_exists(self, fname: str) -> bool:
        return self.notes_path(fname).exists()

    def notes_path(self, fname: str) -> Path:
        return self.notes_root / f"{fname}.md"

    def autocomplete(self, prefix: str, max_tags: int = 10) -> List[str]:
        prefix = prefix.lower()
        tags = [k for k in self._titles.keys() if prefix in k]
        return sorted(tags)[:max_tags]

    def backlinks(self, fname: str) -> List[str]:
        return [
            {
                "title": self.title(b),
                "value": b,
            } for b in self._backlinks[fname]
        ]

    def title(self, fname: str) -> str:
        if fname in self._titles:
            return self._titles[fname]
        return self.default_title(fname)

    def body(self, fname: str) -> str:
        fpath = self.notes_path(fname)
        last_mod_time = fpath.stat().st_mtime

        def get_markdown(fpath: Path) -> str:
            with open(fpath, "r") as f:
                markdown = self.md_ctx.convert("".join(f.readlines()[1:]))
            markdown = re.sub(r"\[\[(.+?)\]\]", self.update_links, markdown)
            return markdown

        if self.ignore_cached:
            markdown = get_markdown(fpath)
        else:
            cached_file = self.cached_file(fname)
            if cached_file.exists() and cached_file.stat().st_mtime > last_mod_time:
                with open(cached_file, "r") as f:
                    return f.read()
            markdown = get_markdown(fpath)
            with open(cached_file, "w") as f:
                f.write(markdown)

        return markdown
