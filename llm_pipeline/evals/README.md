# Evaluation dataset

`dataset.jsonl` — 10 **synthetic** clinical vignettes written for this assignment.
No real patient data, no PHI: ages, findings and results are invented, and the
texts are not derived from any record or publication.

Each line is `{"id", "raw_text", "expected"}`, where `expected` is hand-written
ground truth validated against the same `ClinicalCaseExtraction` contract the
model must satisfy.

Coverage is deliberate: synonym answer keys (case-001/003/005), differentials
with partial credit, all seven finding categories, and one case with unstated
age and sex (case-010) to test that the model returns `null` instead of guessing.

See `../README.md` in the repo root for how to run the harness.
