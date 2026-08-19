#!/usr/bin/env bash
# Публикует демо на GitHub Pages: ветка gh-pages, index.html в корне, PDF рядом.
# Ветка сиротская — история статьи и данных в неё не попадает.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WT="$(mktemp -d)"

python3 "$ROOT/demo/build_site.py"

if git -C "$ROOT" show-ref --verify --quiet refs/heads/gh-pages; then
  git -C "$ROOT" worktree add "$WT" gh-pages >/dev/null
else
  git -C "$ROOT" worktree add --detach "$WT" >/dev/null
  git -C "$WT" checkout --orphan gh-pages >/dev/null
  git -C "$WT" rm -rq --cached . 2>/dev/null || true
fi

find "$WT" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
mkdir -p "$WT/paper"
# В корне ветки ../paper/ ведёт выше корня сайта, поэтому ссылку правим.
sed 's|\.\./paper/pitfall\.pdf|paper/pitfall.pdf|g' "$ROOT/demo/index.html" > "$WT/index.html"
cp "$ROOT/paper/pitfall.pdf" "$WT/paper/pitfall.pdf"
touch "$WT/.nojekyll"   # иначе Jekyll съедает файлы и папки, начинающиеся с _

git -C "$WT" add -A
if git -C "$WT" diff --cached --quiet; then
  echo "нечего публиковать: сайт не изменился"
else
  git -C "$WT" commit -qm "demo site: publish current build" 
  git -C "$WT" push -q origin gh-pages
  echo "опубликовано"
fi
git -C "$ROOT" worktree remove --force "$WT"
