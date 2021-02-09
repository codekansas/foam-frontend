#!/usr/bin/env python

__all__ = ["Backend"]

import copy
import itertools
import logging
import os
import pickle
import re
import sys
from pathlib import Path
from typing import List, Optional

import click
import markdown
import markdown.extensions.codehilite
import markdown.extensions.fenced_code

logger = logging.getLogger(__name__)


def reset_logger() -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    root.addHandler(handler)


class Backlinks:
    """Utility class for efficiently managing backlinks."""

    def __init__(
        self,
        cache_dir: Optional[Path],
        fpaths: List[Path],
    ) -> None:
        if cache_dir is None:
            self.cache_path = None
            self.ignore_cached = True
        else:
            self.cache_path = cache_dir / "backlinks.pkl"
            self.ignore_cached = False
        self.fpaths = fpaths
        self.stem_map = {fpath.stem: fpath for fpath in self.fpaths}
        self.titles = {
            fpath.stem: self.read_title(fpath)
            for fpath in self.fpaths
        }
        self.backlinks = {}
        self.mtimes = {}
        self.load()

    def read_title(self, fpath: Path) -> str:
        with open(fpath, "r") as f:
            title = f.readline()
        if not title:
            return self.default_title(fpath.stem)
        return title[2:].strip()

    def add_backlinks(self, fpath: Path) -> None:
        with open(fpath, "r") as f:
            for match in re.finditer(r"\[\[(.+?)\]\]", f.read()):
                link_to = match.group(1)
                if fpath.stem == link_to:
                    raise ValueError(f"Self-referential backlink: {link_to}")
                if link_to not in self.backlinks:
                    self.backlinks[link_to] = {fpath.stem}
                else:
                    self.backlinks[link_to].add(fpath.stem)

    def remove(self, stem: str) -> None:
        fpath = self.stem_map[stem]
        fpath.unlink()
        self.stem_map.pop(stem)
        logger.info("Removed %s", fpath)
        title = self.titles.pop(stem)

        if stem in self.backlinks:
            for backlink in self.backlinks[stem]:
                with open(self.stem_map[backlink], "r") as f:
                    contents = f.read()
                # Removes the link reference at the bottom.
                contents = re.sub(
                    rf"\[\[{stem}\]\]: {stem}.+\n", "", contents)
                # Removes references to the link.
                contents = re.sub(rf"\[\[{stem}\]\]", title, contents)
                with open(self.stem_map[backlink], "w") as f:
                    f.write(contents)
                logger.info("Updated backlinks in %s", backlink)

        for stem, backlinks in self.backlinks.items():
            if stem in backlinks:
                backlinks.remove(stem)

        self.save()

    def rename(self, old_stem: str, new_stem: str) -> None:
        old_fpath = self.stem_map[old_stem]
        new_fpath = old_fpath.parent / f"{new_stem}.md"
        if old_fpath.parent != new_fpath.parent:
            new_fpath.parent.mkdir(exist_ok=True, parents=True)
            new_stem = new_fpath.stem
        old_fpath.rename(new_fpath)
        self.stem_map.pop(old_stem)
        self.stem_map[new_stem] = new_fpath
        self.titles[new_stem] = self.titles.pop(old_stem)
        logger.info("Renamed %s to %s", old_fpath, new_fpath)

        if old_stem in self.backlinks:
            for backlink in self.backlinks[old_stem]:
                with open(self.stem_map[backlink], "r") as f:
                    contents = f.read()
                new_contents = contents.replace(old_stem, new_stem)
                with open(self.stem_map[backlink], "w") as f:
                    f.write(new_contents)
                logger.info("Updated backlinks in %s", backlink)

            self.backlinks[new_stem] = self.backlinks[old_stem]
            self.backlinks.pop(old_stem)

        for stem, backlinks in self.backlinks.items():
            if old_stem in backlinks:
                backlinks.add(new_stem)
                backlinks.remove(old_stem)

        self.save()

    def load(self) -> None:
        if not self.ignore_cached and self.cache_path.exists():
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

    def save(self) -> None:
        if not self.ignore_cached:
            with open(self.cache_path, "wb") as f:
                pkl_data = {
                    "backlinks": self.backlinks,
                    "mtimes": self.mtimes,
                }
                pickle.dump(pkl_data, f)
    
    def path(self, stem: str) -> Optional[Path]:
        return self.stem_map.get(stem, None)

    def __contains__(self, fstem: str) -> None:
        return fstem in self.backlinks

    def __getitem__(self, fstem: str) -> List[str]:
        return list(sorted(self.backlinks.get(fstem, {})))


class Backend:
    def __init__(self, root_path: str) -> None:
        self.ignore_cached = bool(os.environ.get("IGNORE_CACHED", False))
        if self.ignore_cached:
            logger.info("Ignoring cached files")
            self.cache_dir = None
        else:
            self.cache_dir = self.root_path / ".cache"
            self.cache_dir.mkdir(exist_ok=True)

        self.root_path = Path(root_path)
        self.notes_root = Backend.notes_root()

        self.md_ctx = markdown.Markdown(
            extensions=[
                "tables",
                "fenced_code",
                "codehilite",
                "mdx_math",
                "markdown_checklists.extension",
            ],
            extension_configs={
                "mdx_math": {
                    "enable_dollar_delimiter": True,
                    "add_preview": True,
                },
            },
            tab_length=2,
        )

        self.fpaths = list(self.notes_root.glob("**/*.md"))
        logger.info("Building directory of %d files", len(self.fpaths))
        self._backlinks = Backlinks(self.cache_dir, self.fpaths)

    @staticmethod
    def notes_root() -> Path:
        if "NOTES_ROOT" not in os.environ:
            raise ValueError("Set NOTES_ROOT environment variable "
                             "to point at your notes directory")
        notes_root = Path(os.environ["NOTES_ROOT"])
        if not notes_root.exists():
            raise ValueError(f"Invalid NOTES_ROOT: {notes_root}")
        return notes_root

    def rename(self, old_stem: str, new_stem: str) -> None:
        self._backlinks.rename(old_stem, new_stem)

    def remove(self, stem: str) -> None:
        self._backlinks.remove(stem)

    def render_link(self, href: str, value: str) -> str:
        return f"<a href={href}>{value}</a>"

    def update_links(self, match: re.Match) -> str:
        fname = match.group(1)
        return self.render_link(fname, self.title(fname))

    def default_title(self, fname: str) -> str:
        return fname.replace("-", " ").replace("_", "_").capitalize()

    def cached_file(self, fname: str) -> Path:
        return self.cache_dir / f"{fname}.html"

    def file_exists(self, fname: str) -> bool:
        fpath = self.path(fname)
        return fpath is not None and fpath.exists()

    def autocomplete(self, prefix: str, max_tags: int = 10) -> List[str]:
        prefix = prefix.lower().replace(" ", "-")
        tags = [k for k in self._backlinks.titles.keys() if prefix in k]
        return [k for k in sorted(tags)[:max_tags]]

    def backlinks(self, fstem: str) -> List[str]:
        return [
            {
                "title": self.title(b),
                "value": b,
            } for b in self._backlinks[fstem]
        ]
    
    def path(self, fname: str) -> Optional[Path]:
        return self._backlinks.path(fname)

    def title(self, fname: str) -> str:
        if fname in self._backlinks.titles:
            return self._backlinks.titles[fname]
        return self.default_title(fname)

    def body(self, fname: str) -> str:
        fpath = self.path(fname)
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

    def __contains__(self, fstem: str) -> None:
        return fstem in self._backlinks


if __name__ == "__main__":

    @click.group()
    def cli():
        reset_logger()

    @cli.command()
    @click.argument("prefix")
    @click.argument("new_prefix")
    def rename(prefix: str, new_prefix: str) -> None:
        backend = Backend(Path.cwd())

        for fpath in backend.fpaths:
            if fpath.stem.startswith(prefix):
                new_stem = fpath.stem.replace(prefix, new_prefix)
                backend.rename(fpath.stem, new_stem)
        logger.info("Updated %s to %s", prefix, new_prefix)

    @cli.command()
    @click.argument("stem")
    @click.option("--prefix/--no-prefix", default=False)
    def remove(stem: str, prefix: bool) -> None:
        backend = Backend(Path.cwd())
        if prefix:
            for fpath in backend.fpaths:
                if fpath.stem.startswith(stem):
                    backend.remove(fpath.stem)
        else:
            if stem in backend:
                backend.remove(stem)
                logger.info("Finished removing stem %s", stem)
            else:
                logger.info("Stem %s not found", stem)

    @cli.command()
    def classify() -> None:
        backend = Backend(Path.cwd())
        notes_root = Backend.notes_root()
        categories = {
            str(fpath.parent.relative_to(notes_root))
            for fpath in backend.fpaths
            if fpath.parent != notes_root
        }

        def _input(prompt: str) -> str:
            return input(prompt).strip().lower()

        def get_category(fpath: str) -> Optional[str]:
            category = _input(f"Category for {fpath.stem}: ")
            if category == "delete":
                backend.remove(fpath.stem)
                return None
            if category == "skip":
                return None
            if category in categories:
                return category
            candidates = {c for c in categories if c.startswith(category)}
            if len(candidates) > 1:
                logger.info("Found multiple candidates: %s", candidates)
                return get_category(fpath)
            elif len(candidates) == 1:
                candidate = list(candidates)[0]
                conf = _input(f"Assuming you mean {candidate} ([n] to abort) ")
                if conf == "n":
                    return category
                else:
                    return candidate
            else:
                conf = _input(f"Adding category {category} ([n] to abort) ")
                if conf == "n":
                    return get_category(fpath)
                else:
                    return category

        def print_categories():
            print("-" * len("Categories:"))
            print("Categories:")
            for category in sorted(categories):
                print(f" - {category}")
            print("-" * len("Categories:"))

        print_categories()
        for fpath in sorted(backend.fpaths):
            if fpath.parent != notes_root:
                continue
            if fpath.stem.lower() == "readme":
                logger.info("Skipping README")
                continue
            category = get_category(fpath)
            if category is None:
                logger.info("Skipping category: %s", fpath.stem)
                continue
            categories.add(category)
            if category not in categories:
                print_categories()
            new_stem = f"{category}/{fpath.stem}"
            backend.rename(fpath.stem, new_stem)

    cli()
