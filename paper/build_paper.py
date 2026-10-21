"""Render the versioned Markdown manuscript to a TeX body; no network or model calls."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def escape(text):
    replacements = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$',
                    '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}',
                    '~': r'\textasciitilde{}', '^': r'\textasciicircum{}',
                    '–': '--', '—': '---', '’': "'", '“': '``', '”': "''",
                    '·': r'\textperiodcentered{}'}
    return ''.join(replacements.get(character, character) for character in text)


def inline(text):
    pattern = r'(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\))'
    parts = re.split(pattern, text)
    result = []
    for part in parts:
        if part.startswith('`') and part.endswith('`'):
            result.append(r'\texttt{' + escape(part[1:-1]) + '}')
        elif part.startswith('**') and part.endswith('**'):
            result.append(r'\textbf{' + escape(part[2:-2]) + '}')
        elif part.startswith('*') and part.endswith('*'):
            result.append(r'\emph{' + escape(part[1:-1]) + '}')
        elif re.fullmatch(r'\[[^\]]+\]\([^)]+\)', part):
            label, url = re.fullmatch(r'\[([^\]]+)\]\(([^)]+)\)', part).groups()
            result.append(r'\href{' + url + '}{' + escape(label) + '}')
        else:
            result.append(escape(part))
    return ''.join(result)


def main():
    lines = (ROOT / 'paper.md').read_text(encoding='utf-8').splitlines()
    output = []
    index = next(index for index, line in enumerate(lines) if line == '## Abstract') + 1
    abstract = []
    while index < len(lines) and not lines[index].startswith('## '):
        abstract.append(lines[index])
        index += 1
    output.extend([r'\begin{abstract}', inline(' '.join(abstract).strip()), r'\end{abstract}'])
    references = False
    while index < len(lines):
        line = lines[index]
        if line.startswith('```'):
            block = []
            index += 1
            while index < len(lines) and not lines[index].startswith('```'):
                block.append(lines[index])
                index += 1
            output.extend([r'\begin{quote}\small\begin{verbatim}', '\n'.join(block),
                           r'\end{verbatim}\end{quote}'])
        elif line.startswith('|'):
            rows = []
            while index < len(lines) and lines[index].startswith('|'):
                cells = [cell.strip() for cell in lines[index].strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?', cell) for cell in cells):
                    rows.append(cells)
                index += 1
            columns = len(rows[0])
            widths = {4: [0.18, 0.17, 0.27, 0.25], 5: [0.34, 0.13, 0.11, 0.12, 0.15]}[columns]
            spec = ''.join('p{' + str(width) + r'\linewidth}' for width in widths)
            output.append(r'{\footnotesize\setlength{\tabcolsep}{4pt}\renewcommand{\arraystretch}{1.3}')
            output.append(r'\begin{longtable}{' + spec + r'}\toprule')
            for row_index, row in enumerate(rows):
                output.append(' & '.join(inline(cell) for cell in row) + r' \\')
                if row_index == 0:
                    output.append(r'\midrule\endhead')
            output.extend([r'\bottomrule\end{longtable}', '}'])
            continue
        elif line.startswith('### '):
            title = re.sub(r'^\d+\.\d+\s+', '', line[4:])
            output.append(r'\subsection{' + inline(title) + '}')
        elif line.startswith('## '):
            title = line[3:]
            if title == 'References':
                references = True
                output.extend([r'\section*{References}', r'\begin{enumerate}'])
            elif re.match(r'^\d+\.', title):
                output.append(r'\section{' + inline(re.sub(r'^\d+\.\s+', '', title)) + '}')
            else:
                output.append(r'\section*{' + inline(title) + '}')
        elif references and re.match(r'^\d+\. ', line):
            output.append(r'\item ' + inline(re.sub(r'^\d+\.\s+', '', line)))
        elif references and line.startswith('Primary sources were accessed'):
            output.extend([r'\end{enumerate}', '\n' + inline(line)])
            references = False
        elif line:
            output.append(inline(line) + '\n')
        else:
            output.append('')
        index += 1
    if references:
        output.append(r'\end{enumerate}')
    destination = ROOT / 'latex' / 'paper-body.tex'
    destination.write_text('\n'.join(output) + '\n', encoding='utf-8')
    print(destination)


if __name__ == '__main__':
    main()
