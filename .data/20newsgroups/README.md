# 20 Newsgroups (by-date test, sampled)

- Files: **400** (20 per newsgroup, seed 20260820)
- Gold tree: topic (comp/rec/sci/…) → subtopic (the newsgroup leaf)
- Inbox names are hashes — the model must not see folder names
- Source: [Jason Rennie / 20 Newsgroups](https://qwone.com/~jason/20Newsgroups/)
- Split: `20news-bydate-test` (the usual eval cut)
- This is a **public folder tree** we can run tonight.
- It is **not** the locked Layer 2 gold (that is MultiEURLEX / EUROVOC).
- Headers stripped when a blank line exists (Usenet From/email).

Cite: Lang, K. NewsWeeder (the collection commonly used via
Joachims / Rennie’s by-date redistribution).
