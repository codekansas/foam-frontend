#!/usr/bin/env python

from typing import Optional

from flask import Flask, abort, render_template

from backend import Backend

app = Flask(__name__)

backend = Backend(app.root_path)


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@app.route("/")
@app.route("/<name>")
def page(name: Optional[str] = None) -> str:
    if name is None:
        name = "readme"

    if not backend.file_exists(name):
        abort(404, description=f"Page not found: {name}")

    title = backend.title(name)
    body = backend.body(name)
    backlinks = backend.backlinks(name)

    return render_template(
        "page.html",
        title=title,
        body=body,
        backlinks=backlinks,
    )


if __name__ == "__main__":
    app.run()
