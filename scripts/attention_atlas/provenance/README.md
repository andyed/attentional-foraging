# Provenance: the final-approach baseline

`compute-final-approach.py` is a byte-identical copy of the script that produced
`docs/visualizations/evidence/final-approach/` (the cohort CSV and the prior
target-overlap baseline that every atlas gate traces back to). Its SHA-256,
`01db9e57063a4efbfed646ebb65d81aef9814b8fbbc820965d1e89067b54d2c2`, matches the
hash recorded in that summary's `provenance.source_hashes`.

It is kept unmodified so the recorded hash stays checkable, which means it
still carries the absolute paths of the working session in which it ran. It is
a record of how the baseline was made, not part of the rebuild: the atlas
producers read its saved outputs and never run it. To rerun it, adapt the paths
into a new script and compare against the saved summary before replacing anything.
