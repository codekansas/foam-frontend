#!/usr/bin/env python

import os
from pathlib import Path

import markdown
import markdown.extensions.fenced_code
from flask import Flask
from pygments.formatters import HtmlFormatter

app = Flask(__name__)

NOTES_ROOT = Path(os.environ["NOTES_ROOT"])


@app.route("/<name>")
def page(name: str) -> str:
    readme_file = open(f"{name}.md", "r")
    md_template_string = markdown.markdown(
        readme_file.read(),
        extensions=["fenced_code", "codehilite"],
    )

    formatter = HtmlFormatter(style="emacs", full=True, cssclass="codehilite")
    css_string = formatter.get_style_defs()
    md_css_string = "<style>" + css_string + "</style>"
    md_template = md_css_string + md_template_string
    return md_template


@app.route("/")
def index() -> str:
    return page("readme")


if __name__ == "__main__":
    app.run()
