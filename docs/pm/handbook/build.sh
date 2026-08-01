#!/usr/bin/env bash
# Build the PM handbook PDF. Two pdflatex passes so the table of contents and
# cross-references resolve on the second run. Mirrors the two-pass compile the
# OsdagBridge app itself uses in core/reports/report_generator.py.
set -euo pipefail

cd "$(dirname "$0")"
DOC="osdagbridge-pm-handbook"

pdflatex -interaction=nonstopmode -halt-on-error "$DOC.tex" >/dev/null
pdflatex -interaction=nonstopmode -halt-on-error "$DOC.tex" >/dev/null

# Drop the aux files; keep the .tex and the built .pdf (both committed).
rm -f "$DOC".{aux,log,out,toc}

echo "Built $DOC.pdf"
