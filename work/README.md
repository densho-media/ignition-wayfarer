# work/

Unapproved work, one folder per task, named like its branch (`claude/eye-layout` → `work/eye-layout/`). AGENTS.md "Where things go"
is the rule; this is the short form.

```
work/<task>/
  NOTES.md               function, fixed constraints, unknowns, design freedom, decisions and open owner questions
  *.py                   study code (reads data/ and src/wayfarer/, writes into runs/ or this folder)
  WORK_<TASK>.blend      the working file (not in Git)
  REVIEW_<TASK>.blend    the one owner review file: packed, opens on the change, nothing to run (not in Git)
```

- Nothing in `src/`, `tests/`, `tools/`, `godot/`, `web/` or CI reads `work/`.
- Text and code here are committed on the task branch; `.blend` files are ignored by Git and reach the owner as a copied file.
- On approval: the chosen form goes into the generators and `data/`, kept numbers into `references/evidence/<task>.json`, the
  folder is deleted and the branch squashed onto `main`. On `main` this README is the only file here.
- Retired studies: `git show 038ae90:src/wayfarer/studies/<name>.py` restores one.
