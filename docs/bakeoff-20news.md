# Organize bake-off (20 Newsgroups gold)

Same 400 hashed files. Same cached `tags.json`. Lightning / llama.cpp.
No re-tag. Primary L1 is the score that matters — any-home inflates
when a file sits in three folders.

| Method | Nodes | Homes/file | Primary L1 | + religion≈belief/society | Any-home L1 | Unmapped | Ghost files |
|---|---:|---:|---:|---:|---:|---:|---:|
| v1 compact (original) | 22 | 3.42 (max 7) | 17.5% (70/400) | 23.5% | 64.0% | 2 | 0 |
| v2 A+B cluster stitch | 18 | 3.23 (max 7) | 11.8% (47/400) | 18.0% | 47.0% | 2 | 0 |
| v3 A+B + fold 1-file | 18 | 3.23 (max 7) | 11.8% (47/400) | 18.0% | 47.0% | 2 | 0 |
| v4 RALP 3 rounds | 21* | 3.09 (max 8) | 37.5% (150/400) | 38.2% | 66.0% | 2 | 180 |

\*RALP `meta.nodes` is stale (21). The walked tree is **274 nodes**, depth 5.

## What each method is

| Id | What ran | Model calls |
|---|---|---|
| v1-compact | Original Pass B: 180 frequent raw tags → one JSON tree | 1 stitch |
| v2-ab | Normalize synonyms, cluster, stitch cluster labels | 1 stitch |
| v3-ab-fold | v2 + fold 1-file children in code | 0 extra |
| v4-ralp | v2-style stitch + 3 audit/apply/revise rounds | already done |

## Majority primary label per gold topic

### compact-frequent-tags

- **belief** → Religious Discussion (7), Needs review (7)
- **computing** → Needs review (58), Computing History (16)
- **debate** → Needs review (26), Usenet 1993 (20)
- **marketplace** → Needs review (10), Vintage Electronics (6)
- **recreation** → Sports Discussion (25), Needs review (18)
- **science** → Needs review (46), Email 1990s (7)
- **society** → Religious Discussion (17), Needs review (2)

### normalize-cluster-compact

- **belief** → Religious Discussions (8), Needs review (8)
- **computing** → Needs review (67), Alternative Technology & Computing (11)
- **debate** → Needs review (32), Usenet 1993 Discussions (21)
- **marketplace** → Needs review (11), Alternative Technology & Computing (7)
- **recreation** → Needs review (29), Sports Discussion (27)
- **science** → Needs review (53), Usenet 1993 Discussions (7)
- **society** → Religious Discussions (16), Needs review (2)

### v3 A+B + fold (same tree as v2)

Same majority labels as v2. Fold found **zero** one-file children.

### ralp-3rounds

- **belief** → Philosophical & Cultural Debates (4), Theological Debates (3)
- **computing** → Software, Algorithms & Resources (11), Hardware Troubleshooting & Repairs (10)
- **debate** → Philosophical & Cultural Debates (9), Political & Policy Debate (6)
- **marketplace** → Listings & Classified Ads (8), Non-Technical & Miscellaneous (4)
- **recreation** → sports-hockey (9), sports (6)
- **science** → Needs review (9), Software & Networking (5)
- **society** → Theological Debates (3), Religion as Lens for Broader Issues (2)

