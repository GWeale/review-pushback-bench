# Paper sources

The readable manuscript is [paper.md](paper.md). It is the canonical prose source. [references.bib](references.bib) provides reusable citation records; [sources.json](sources.json) records the primary pages checked and their use.

To reproduce the PDF from a TeX installation with the packages used in `latex/main.tex`:

```powershell
python paper/build_paper.py
```

Then, from `paper/latex/`, run twice:

```powershell
pdflatex -interaction=nonstopmode -halt-on-error -no-shell-escape main.tex
```

The result is `paper/latex/main.pdf`; the release copy is `paper/review-pushback-bench.pdf`. The generated `paper-body.tex` must be rebuilt after a Markdown change. The paper's tables distinguish synthetic policy checks from actual model measurements. A source build alone does not establish that the experiments were performed.

This is a public technical report, not a peer-reviewed publication. AI assistance and the limits of dataset validation are disclosed in the manuscript.
