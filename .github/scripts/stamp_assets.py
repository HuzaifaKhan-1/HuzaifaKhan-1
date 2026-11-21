"""Adds a content fingerprint (?v=<hash>) to every local asset link in README.md.

A changed file gets a new URL, so browsers and GitHub's image cache fetch it
at once; unchanged files keep their URL and stay cached.
Usage (from the repo root):  python .github/scripts/stamp_assets.py
"""
import hashlib
import pathlib
import re

readme = pathlib.Path('README.md')
text = readme.read_text(encoding='utf-8')


def stamp(match):
    attr, path = match.group(1), match.group(2)
    digest = hashlib.sha1(pathlib.Path(path).read_bytes()).hexdigest()[:8]
    return f'{attr}="{path}?v={digest}"'


new = re.sub(r'\b(src|srcset)="(assets/[^"?]+)(?:\?v=[0-9a-f]+)?"', stamp, text)
if new != text:
    readme.write_text(new, encoding='utf-8')
count = len(re.findall(r'="assets/[^"?]+\?v=', new))
print(f'{count} asset links stamped')
