#!/bin/sh
# Shows what each view of a base returns in Obsidian, as markdown tables, with `this` bound to a note.
#
# A view embedded in a note sees that note as `this`, but `obsidian base:query` runs the base on its
# own, where `this` is the base file. This script queries a temporary copy of the base in which `this`
# is replaced by the note, then deletes the copy. Obsidian must be running, with the vault open.
#
#   scripts/query_base.sh <vault name> <vault folder> <base path in the vault> <note path in the vault> [view]
#
# e.g. scripts/query_base.sh teach-me ~/vault bases/course.base courses/x/course-x.md Plan
# A view that doesn't parse prints its error instead of a table.
set -eu
vault=$1; dir=$2; base=$3; note=$4; only=${5:-}
tmp="bases/_query-$$.base"
sed -e "s#this\.file\.folder#\"$(dirname "$note")\"#g" -e "s#this\.file#file(\"$note\")#g" "$dir/$base" > "$dir/$tmp"
trap 'rm -f "$dir/$tmp"' EXIT
cd /tmp  # the CLI picks the vault of the current folder otherwise
obsidian vault="$vault" eval code="new Promise(r => setTimeout(() => r(1), 1500))" > /dev/null  # let Obsidian index the copy
grep -E "^    name: " "$dir/$tmp" | sed -e 's/^    name: //' -e 's/^"\(.*\)"$/\1/' | while read -r view; do
  if [ -n "$only" ] && [ "$only" != "$view" ]; then continue; fi
  echo "== $view"
  obsidian vault="$vault" base:query path="$tmp" view="$view" format=md < /dev/null  # it would read the views otherwise
done
