"""Build the atlas entry page, the project overview and the process explanation from repository Markdown.

Repository links are rewritten: atlas files stay relative, other repository
files point at GitHub. Headings get GitHub-style ids so in-page links work.
The published entry page leaves out the local viewing and rebuild sections
of the atlas guide; those stay in the Markdown for readers of the repository.
"""
import re

import mistune

import atlas_core as core
from atlas_core import ATLAS, ROOT

REPO_BLOB = 'https://github.com/andyed/attentional-foraging/blob/main/'
DEVELOPER_SECTIONS = ('View locally', 'Rebuild and verify')
style = ('*{box-sizing:border-box}body{margin:0;background:#fafaf8;color:#222;font:500 19px/1.6 Arial,sans-serif}'
         'main{max-width:1120px;margin:auto;padding:32px 30px}h1{font-size:42px;line-height:1.15}h2{margin-top:42px;line-height:1.25}'
         'a{color:#00505e;text-underline-offset:3px}a:focus-visible,.table-wrap:focus-visible{outline:3px solid #782650;outline-offset:4px}'
         'img{max-width:100%;height:auto}nav{display:flex;gap:24px;flex-wrap:wrap}nav a{min-height:44px;display:inline-flex;align-items:center}'
         '.table-wrap{overflow-x:auto}table{border-collapse:collapse}td,th{padding:10px;text-align:left;border-bottom:1px solid #999}'
         'pre{overflow-x:auto;background:#eeefea;padding:18px;font-size:16px}code{overflow-wrap:anywhere}p,li{max-width:86ch}'
         '@media(max-width:600px){main{padding:22px 18px}h1{font-size:32px}}')
NAV = ('<nav aria-label="Atlas"><a href="./">Atlas</a><a href="information-space-poster/">Time and space</a>'
       '<a href="gaze-cursor-echo/">Sequences and timing</a><a href="not-a-cascade.html">Not a cascade</a>'
       '<a href="readme.html">Project overview</a></nav>')


def page(title, body):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width,initial-scale=1"><title>{title}</title><style>{style}</style></head>'
            f'<body><main>{NAV}{body}</main></body></html>')


def slug(text):
    """GitHub's heading anchor: lowercase, punctuation dropped, spaces to hyphens."""
    text = re.sub(r'<[^>]+>', '', text).strip().lower()
    return re.sub(r'\s', '-', re.sub(r'[^\w\s-]', '', text))


def without_sections(markdown, titles):
    out, skip = [], False
    for line in markdown.split('\n'):
        if line.startswith('## '):
            skip = line[3:].strip() in titles
        if not skip:
            out.append(line)
    return '\n'.join(out)


def render(source, markdown):
    body = mistune.create_markdown(escape=False, plugins=['table'])(markdown)

    def resolve(m):
        kind, ref = m.groups()
        if ref.startswith(('https:', 'http:', '#', 'mailto:')):
            return m.group(0)
        path, _, fragment = ref.partition('#')
        resolved = (source.parent / path).resolve()
        if resolved == ROOT / 'docs/not-a-cascade.md':
            target = 'not-a-cascade.html'
        elif resolved == ROOT / 'README.md':
            target = 'readme.html'
        elif resolved == core.CANONICAL_ATLAS / 'README.md':
            target = 'index.html'
        elif resolved.is_relative_to(core.CANONICAL_ATLAS):
            target = resolved.relative_to(core.CANONICAL_ATLAS).as_posix()
            if resolved.name == 'methods.md':
                target = target.replace('methods.md', 'methods.html')
        elif resolved.is_relative_to(ROOT):
            target = REPO_BLOB + resolved.relative_to(ROOT).as_posix()
        else:
            raise ValueError(ref)
        return f'{kind}="{target}{"#" + fragment if fragment else ""}"'

    body = re.sub(r'(href|src)="([^"]+)"', resolve, body)
    body = re.sub(r'<h([1-6])>(.*?)</h\1>', lambda m: f'<h{m[1]} id="{slug(m[2])}">{m[2]}</h{m[1]}>', body)
    return body.replace('<table>', '<div class="table-wrap" tabindex="0"><table>').replace('</table>', '</table></div>')


guide = core.CANONICAL_ATLAS / 'README.md'
guide_md = without_sections(guide.read_text(), DEVELOPER_SECTIONS) + (
    '\n\nLocal viewing, rebuild commands and verification are described in the '
    f'[atlas guide on GitHub]({REPO_BLOB}docs/visualizations/README.md).\n')
for source, markdown, output, title in [
        (ROOT / 'README.md', (ROOT / 'README.md').read_text(), 'readme.html',
         'Attentional Foraging in Search: Initial Sampling and Recurrent Evaluation'),
        (guide, guide_md, 'index.html', 'Search process: two linked posters'),
        (ROOT / 'docs/not-a-cascade.md', (ROOT / 'docs/not-a-cascade.md').read_text(), 'not-a-cascade.html',
         'Not a cascade: examination includes returns')]:
    (ATLAS / output).write_text(page(title, render(source, markdown)))
print(ATLAS / 'index.html')
