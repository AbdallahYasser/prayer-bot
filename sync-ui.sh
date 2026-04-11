#!/bin/bash
# Copy Gemini's UI edits from the test folder into the real project.
# Run this after Gemini finishes a UI change, then ask Claude to commit + deploy.

SRC="/Users/abdullahwafik/Downloads/projects/gemini/test ui"
DST="$(dirname "$0")/web/src/static"

cp "$SRC/index.html" "$DST/"
cp "$SRC/app.js"     "$DST/"
cp "$SRC/style.css"  "$DST/"

echo "Synced UI from test folder → web/src/static/"
git -C "$(dirname "$0")" diff --stat -- web/src/static/
