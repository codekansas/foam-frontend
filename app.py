#!/usr/bin/env python

import json
from typing import Optional

from flask import Flask, Response, abort, render_template, request

from backend import Backend

app = Flask(__name__)

backend = Backend(app.root_path)


@app.route("/autocomplete")
def autocomplete() -> Response:
    if "prefix" not in request.args:
        return Response(json.dumps([]), mimetype="application/json")
    titles = backend.autocomplete(request.args["prefix"])
    return Response(json.dumps(titles), mimetype="application/json")


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@app.route("/")
@app.route("/<name>")
def page(name: Optional[str] = None) -> str:
    if name is None or name == "index":
        name = "readme"

    if not backend.file_exists(name):
        abort(404, description=f"Page not found: {name}")

    return render_template(
        "page.html",
        title=backend.title(name),
        body=backend.body(name),
        backlinks=backend.backlinks(name),
        note_name=f"{name}.md",
        note_path=backend.path(name),
    )


if __name__ == "__main__":
    app.run()
