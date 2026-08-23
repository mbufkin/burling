# How the U.S. military files documents

**Question:** Do they discover a browse tree from a pile, or assign each
file into a pre-existing file plan? What is written down?

**Ticket date:** 2026-08-21
**What you are looking at:** Burling turns a stranger’s dump into
main type → subtype. The military already has a clerk SOP for that
job. This note traces the SOP to the owning manuals. Claims are
from official .mil / archives.gov / govinfo.gov / ecfr.gov PDFs and
HTML only.

Sibling notes: [browse-map.md](browse-map.md),
[tag-then-stitch.md](tag-then-stitch.md),
[PRIOR-ART.md](PRIOR-ART.md).

---

## What this means for Burling

**They do not discover topics from a pile.** Every service assigns
each record into a **prescribed file plan** that already exists
before the document is written. The plan is a numbered subset of a
NARA-approved records schedule. The clerk’s job is: read the
subject → pick the one closest code → put it in that numbered
folder. Year, office, and Secret/TS are **not** top-level browse
heads. They are metadata or storage constraints on top of the
subject code.

| Burling question | What the manuals prescribe |
|---|---|
| Discover a tree, or use a pre-existing plan? | **Pre-existing plan.** OSD: every office “shall have a file plan documenting the records accumulated.” Navy: “Only approved SSICs will be assigned.” Army: match records to a valid record number; unidentified files go to the records manager, not a new invented type. |
| Functional or topical (20 Newsgroups)? | **Functional.** Personnel, ops, logistics, finance, medical — the mission functions of the department. Not “hockey / religion / cars.” |
| One home or many? | **One primary home.** Navy: the SSIC that “most closely describes that record’s subject.” Army: one record number; a DA Form 1613 cross-reference if the doc relates to a second action. Air Force: “one disposition authority (table and rule) per” primary folder. OSD allows the *same copy* under two file numbers only when the office uses it for two different functions (contract file vs. air-warfare file). That is two business uses, not two topics. |
| Who assigns the code? | **The author at creation**, not a later sorter. Navy: “When you create a record, include the SSIC.” The action officer “adds the SSIC when writing a document.” Army: the writer puts the record number on the memo next to the office symbol (`ISES–RM (25-50a)`). |
| Required metadata | Subject code (SSIC / RN / table-and-rule), office symbol / originator, date, title, disposition authority. Classification is a **separate** field. |
| Steal for Burling | One primary home. Prescribed top-level types (functional, ~8–15). Ignore channel and year as heads — they are cutoffs inside a folder. Clerk SOP: read the subject line, put it in the numbered folder. Classification / Secret is orthogonal to the browse tree. |

The military analog of Burling’s “main type” is the **major subject
group** (Navy SSIC 1000/2000/3000…) or the **records series** (OSD
100/200/300…; Army prescribing-directive family). The analog of
“subtype” is the primary → secondary → tertiary cut (Navy
`5000 → 5200 → 5210 → 5211`) or the file number / table-and-rule.

They do **not** do TaxoGen. They do not let the pile invent
“1990s Internet Culture.” A new type is a formal change request
to the records office, then NARA.

---

## 1. Navy / Marine Corps — SSIC (the cleanest clerk SOP)

**Owning document for the codes:** SECNAV M-5210.2, *Department of
the Navy Standard Subject Identification Code (SSIC) Manual*,
August 2018.
https://www.secnav.navy.mil/doni/SECNAV%20Manuals1/5210.2.pdf

**Not** SECNAV M-5210.1. M-5210.1 is the *Records Management
Manual* (life-cycle + NARA disposition schedules). DON CIO states
that plainly (SECNAV M-5210.1, September 2019):
https://www.doncio.navy.mil/contentview.aspx?id=707
The codes themselves live in M-5210.2. M-5210.2’s own foreword
says it “specifies filing and record maintenance procedures and
provides SSICs” and is “to be used in conjunction with” M-5210.1.

### The 13 series (M-5210.2, Part II §2)

The DON SSIC system “is divided into 13 major subject groups.”
An SSIC is “a four or five digit number that stands for the
subject of a document.”

| Series | Title | What the manual says it includes |
|---|---|---|
| 1000–1999 | Military Personnel | Admin of military personnel only. Civilian → 12000. Both → 5000. |
| 2000–2999 | Information Technology and Communications | IT matters; communication systems and equipment. |
| 3000–3999 | Operations and Readiness | Plans, fleet ops, training and readiness, warfare techniques, operational intelligence, R&D, geophysical/hydrographic support. |
| 4000–4999 | Logistics | Procurement, supply, redistribution/disposal, travel, maintenance, construction, production/mobilization planning, FMS. |
| 5000–5999 | General Administration and Management | Org/management, general personnel (civilian *and* military), records, security, relations, law, office services, publishing. |
| 6000–6999 | Medicine and Dentistry | Physical fitness, general/special/preventive medicine, dentistry, medical equipment. |
| 7000–7999 | Financial Management | Budgeting, disbursing, accounting, auditing, industrial finance, statistical reporting. |
| 8000–8999 | Ordnance Material | Ammunition, missiles, nuclear weapons, fire control, combat vehicles, underwater ordnance. |
| 9000–9999 | Ships Design and Material | Ship design/characteristics; ships material and equipment. |
| 10000–10999 | General Material | Material not in a specialized group: personnel material, machinery/tools, audiovisual, metals, fuels, electrical, diving. |
| 11000–11999 | Facilities and Activities Ashore | Ashore structures, fleet/transportation facilities, heavy equipment, utilities. |
| 12000–12999 | Civilian Personnel | Civilian personnel only. |
| 13000–13999 | Aeronautical and Astronautical Material | Aircraft/astronautic parts, instruments, armament, weapons systems, vehicles. |

This is a **functional** tree (who does the work / what mission
function produced the paper), not a topical newsgroup tree.

### One code, at creation (M-5210.2, Introduction + Part II §§1, 4)

> “An SSIC is required on all DON records including, but not
> limited to, letters, messages, directives, forms, and
> reports/information collections. Only approved SSICs will be
> assigned.”

> “The requirement to assign an SSIC applies to any record
> regardless of its format and medium.”

> “When you create a record, include the SSIC that most closely
> describes that record’s subject. Also, consider the document’s
> subject, its purpose or significance, and the SSIC used for
> similar documents.”

> “As specified in SECNAV M-5216.5 … the action officer adds the
> SSIC when writing a document, or places the SSIC along the
> right hand edge of documents not identified with an SSIC at
> the time of creation.” (Part I, §1-4)

That is the one-home / author-assigns rule. There is no later
discovery pass that invents a 14th series from the pile.

### How the number nests (Part II §3)

`5000` General Administration and Management (major group /
zeros = general)
`5200` Management Programs and Techniques (primary)
`5210` Records Management (secondary)
`5211` Filing, Maintenance, Protection, Retrieval, and Privacy
Act Systems (tertiary)

“The last three digits of an SSIC number designate subject
levels.” Some groups stop at primary; others go deep.

### What a “file plan” is (Introduction §4)

> “A file plan is an organizational scheme for how records are
> organized. The plan specifies the identifying number, title,
> or description and disposition authority of files held in an
> organization. A file plan allows users to select categories
> in which records are filed and assign records to these
> categories.”

Inside the DON, “the schedule numbers provide the basis for
organizational file plans.” The office does not invent
categories. It **selects** from the schedule.

### Clerk SOP — paper in a folder (Part I, Chapter 1)

This *is* the Navy filing-clerk manual (Navy only; Marines follow
MCO 5210.11, which this research did not open):

1. Inspect: action complete? strip envelopes and routing slips.
2. Assemble: staple; remove SF 703/704/705 cover sheets unless
   still in suspense.
3. Mark the SSIC (already on the letter, or write it on the
   right edge).
4. File under the **schedule number** that crosswalks from that
   SSIC. Subdivide *inside* the folder by date, simple number,
   subject alpha, or name — not as a new top-level type.
5. Classified and unclassified go in **separate containers**.
   Same SSIC, different drawer. Classification is not a series.

Retrieval request (Part I, Chapter 4): SSIC and serial, writer
name, date, requester. That is the finder’s metadata set.

---

## 2. Army — ARIMS record numbers + DA Pam 25-403 (the clerk SOP)

**Policy:** AR 25-400-2, *Army Records Management Program*,
18 October 2022 (effective 18 November 2022). Title changed
from “The Army Records Information Management System (ARIMS).”
https://armypubs.army.mil/epubs/DR_pubs/DR_a/ARN38446-AR_25-400-2-001-WEB-2.pdf
Landing page: https://armypubs.army.mil/ProductMaps/PubForm/Details.aspx?PUB_ID=1021513

**Clerk SOP:** DA Pam 25-403, *Army Guide to Recordkeeping*,
10 November 2022 (admin revision noted 9 February 2023).
This is the current “Army filing manual.”
https://armypubs.army.mil/epubs/DR_pubs/DR_a/ARN38438-PAM_25-403-002-WEB-3.pdf

AR 25-400-2 §1-3: “Procedures associated with this regulation
are found in DA Pam 25–403.”

### How a file is numbered

DA Pam 25-403 glossary:

> **Record number.** “The number assigned under ARIMS to a
> specific series of records. The number is based on the
> prescribing directive specifying they be created. Synonymous
> with file number.”

AR 25-400-2 glossary (same idea): “The number assigned to an
RRS–A record title describing a unique category of record
information.”

Examples the pamphlets themselves use: `25-50a` (correspondence
delegations), `25-400-2d` (disposition-standard exceptions),
`37-1a` / `37-49b` (finance allocations). The number is the
**regulation that created the record type**, plus a letter for
the series under that regulation. That is a functional /
directive taxonomy, not a discovered topic.

**MARKS:** the 2022 AR and Pam **do not cite** the Modern Army
Recordkeeping System. Do not claim the current AR still names
MARKS. What survived is the prescribing-directive record number
(`25-50a`). AR 25-400-2’s own history line says it supersedes
the 2 October 2007 ARIMS edition.

### Office Records List = the office’s file plan

AR 25-400-2 glossary, **Office records list**:

> “A list of the specific RRS–A record titles and numbers
> describing record information accumulated or generated in an
> office. … It is prepared within each element where records
> are accumulated or generated by using the ARIMS office
> records lists and folders module.”

DA Pam 25-403: “An approved ORL which lists all the RNs for
information that could be created or maintained by the [office]
… The ORL should be used to set up electronic and hardcopy
files.” Evaluation checklist: “Are ORLs prepared using the
‘ORLs and Folders’ tab in ARIMS and approved by the servicing
RMO?” “Are all unidentified files brought to the attention of
the RM?”

So: the Army does not browse-discover. Each office **checks
out** the subset of the Army schedule it actually creates. A
file with no RN is an error, not a new type.

### One home, with a pointer if needed (DA Pam 25-403 §5-3)

> “A records cross reference is filed under one RN to show the
> location of material filed elsewhere. Prepare a DA Form 1613
> (Records Cross Reference) only when essential to retrieving
> information.” Use when “a document is related to more than
> one action,” when classified material relates to unclassified
> files, or when a document “has been changed from one RN to
> another RN.”

Primary home + optional pointer. Not two browse folders.

### Clerk SOP — put the paper in the folder (DA Pam 25-403 Ch. 5)

§5-2, before filing: examine that the action is complete; strip
envelopes and extra copies; assemble with the most recent action
on top; staple.

§5-6, hardcopy labels (generated in ARIMS): disposition code,
ACRS subseries, **RN and title and current year**, disposition
instructions, Privacy Act yes/NA, barcode for long-term, location
if not in that folder. Year is on the label of an already-numbered
folder. It is not a root type.

§2-12: “Unless specified by the prescribing directive, records
can be filed either chronologically or alphabetically as suits
the business practices of the individual office.” Arrangement
*inside* the RN, not a new RN.

§2-15 inventory: physically inspect → record essentials →
identify duplicates → **“Match the records to the appropriate
RN and/or records disposition schedule.”**

§4-15 electronic file names: Access (Unclassified/CUI) —
Organization (office symbol) — Content — Date — Version —
extension. Classification and office symbol are filename
fields, not folder heads.

---

## 3. Air Force / Space Force — AFRIMS “inventory of records” + table and rule

**Owning document:** AFI 33-322, *Records Management and
Information Governance Program*, 23 March 2020, as amended by
AFI33-322_DAFGM2025-01 (26 June 2025). The DAFGM is issued
“By Order of the Secretary of the Air Force” and applies DAF-wide
(MAJCOMs / FLDCOMs), i.e. Air Force and Space Force, until an
interim change rewrites the AFI.
https://static.e-publishing.af.mil/production/1/saf_cn/publication/afi33-322/afi33-322.pdf

The current AFI’s working name for the office file plan is
**inventory of records**, maintained in the Air Force Records
Information Management System (AFRIMS). The Records Disposition
Schedule (RDS) inside AFRIMS is “the authorized source for record
dispositions; supplements to the Records Disposition Schedule
are not authorized” (AFI 33-322 ¶3.2.1).

### How they file (AFI 33-322 ¶3.3, ¶4.6)

> “Primary folder titles reflect the inventory of records title;
> sub-folders are not numbered … and are not reflected on the
> inventory of records. Sub-folders will contain only the record
> types described in the table and rule of the primary folder.
> (T-1). Segregation of records by disposition is required by
> the National Archives.”

> “The e-filing system must mirror the current office inventory
> of records. (T-1).”

> “Each document in electronic form must be identified
> sufficiently to enable authorized personnel to retrieve,
> protect, and carry out its disposition. (T-1).”

External label on media (¶4.6.5.1): security classification,
**table and rule from the RDS**, originating office symbol,
title, begin/end dates, software, hardware.

Inventory titles “will not contain sensitive, classified, For
Official Use Only, or Privacy Act information” (¶3.3.1).
Classification is an access/marking problem, not a folder name.

Year appears as cutoff: “Subdivide each directory by fiscal year
or calendar year” *after* the record is already under its table
and rule (¶4.6.6).

If the action officer is unsure: an optional “e-file box”
numbered `00` at the top of the tree; commander must get those
files into the right folder within 48 hours (¶4.6.7). That is
a suspense bin, not a discovered topic.

AF Form 525 is the form to **recommend a change** to the RDS
(table of contents; Attachment 2). New types go up the chain.
They are not mined from a dump.

---

## 4. DoD-wide — what a “file plan” is in the software

### DoDI 5015.02 (policy)

DoDI 5015.02, *DoD Records Management Program*, 24 February 2015,
as amended (2017 update cited in NARA SAORM reports). Official
listing: https://www.esd.whs.mil/RIM/

The PDF at the usual `501502p.pdf` path did not load in this
pass. What is citable from other official documents:

- NARA inspection report (April 2020) quotes DoDI 5015.02:
  “The information and intellectual capital contained in DoD
  records will be managed as national assets.”
  https://www.archives.gov/files/records-mgmt/pdf/dod-js-ccmds-inspection-report-2020.pdf
- DoDM 8180.01 and DTM-22-001 both implement / fold into
  DoDI 5015.02. DTM-22-001 (3 March 2022, Change 2):
  https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dtm/DTM-22-001.PDF

### DoD 5015.02-STD — cancelled

DoD 5015.02-STD, *Electronic Records Management Software
Applications Design Criteria Standard*, 25 April 2007, was the
RMA design standard (categorize, locate, dispose). JITC still
describes it on an official page and previously hosted the PDF:
https://jitc.fhu.disa.mil/projects/rma/stdtesting.aspx
https://jitc.fhu.disa.mil/projects/rma/index.aspx
(index states the test program is terminated because the STD
was cancelled).

**Successor:** DoDM 8180.01, *Information Technology Planning
for Electronic Records Management*, 4 August 2023. “Reissues
and Cancels: DoD 5015.02-STD … April 25, 2007.”
https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dodm/818001m.PDF

DoDM 8180.01 glossary:

> **file plan** — “A subset of the organization’s records
> schedules that includes a listing of records schedule items
> that apply to the office.”

Planning §3.2.b: for any IT system the provider “must contact
customer records staff for the associated records schedules or
file plans that categorize any data in the system, identify
records that will be managed in the system, and document the
associated legal retentions.”

That is the software definition: a file plan is **not** a
clustering of the corpus. It is the office’s checked-out rows
from the schedule.

NARA endorsed the 2007 STD for all federal agencies
(Bulletin 2008-07) and later revoked that endorsement
(Bulletin 2022-01) because the STD was being replaced:
https://www.archives.gov/records-mgmt/bulletins/2008/2008-07.html
https://www.archives.gov/records-mgmt/bulletins/2022/2022-01

### OSD clerk SOP — the numeric file plan, written out

*Office of the Secretary of Defense Records and Information
Management Program Primer*, 12 December 2023. First-party WHS
PDF:
https://www.esd.whs.mil/Portals/54/Documents/OSD%20RIM%20PRIMER_12%20Dec%202023_(F).pdf

This is the closest thing to “how a Pentagon clerk puts a paper
in a folder” at OSD.

**Numeric filing (Primer §4.5–4.6).** “The OSD RDS is the only
filing system authorized. … Modification of the numbering
system is not permitted.” The RDS is “arranged in a hybrid
functional and organizational file system. The implementation
of the schedule, however, is based on function.” Three levels:
Record Series (`100`, `200`, `300`…) → Records Category
(`101`, `202`…) → File Number (`101-01.1`, `202-70`).

Examples the Primer itself prints (Tables 1–3) — do not invent
others:

| Series | Title (Primer’s examples) |
|---|---|
| 100 | General Office Records |
| 200 | Management and Operations |
| 300 | USD(Comptroller) |
| 400 | DoD General Counsel |

Categories e.g. `202` Office Personnel Files, `203` Information
Management Files. File numbers e.g. `201-01.1` Organization
Planning Files.

**File plan (§4.7).** “The file plan provides a comprehensive
system of identification, maintenance, and disposition of all
records … created or received within an organizational unit.
Every office … shall have a file plan.” Updated at least
annually. File number, title, and disposition authority
“must be cited exactly as written in the OSD RDS (no changes
are permitted).”

Minimum columns (Figure 1): File Number | Title and
description | Cutoff/retention/disposition | Disposition
authority | **Records Classification** | Essential (y/n) |
Media | Privacy Act SORN | Location(s).

Classification is a **column on the plan**, not the plan.

**One home vs two uses (§4.9).** A contractor report “may be
stored … under two (or more) file numbers” — `206-09.1`
(financial transaction / procuring goods) **and** `1308-01`
(Air Warfare Files) — because the *same document serves two
office functions*. That is the exception, and it is function,
not topic. Dummy folders (§4.13) hold the label for a file
number; year-only labels go on the later folders. Year is
again not a root.

**How the clerk arranges inside a number (§4.8):** pick the
series → pick the file number → then arrange by subject, case,
date, number, name, geography, or function “based on the
primary function by which the file will be recalled.”
“Modification or deviation of file numbers is not authorized.”

---

## 5. How a document is labeled (correspondence), not just stored

Filing codes are printed on the letter **when it is written**.

### Army — AR 25-50

AR 25-50, *Preparing and Managing Correspondence*, 10 October
2020 (later admin revisions through 4 October 2024).
https://armypubs.army.mil/epubs/DR_pubs/DR_a/ARN42124-AR_25-50-007-WEB-13.pdf
Landing: https://armypubs.army.mil/ProductMaps/PubForm/Details.aspx?PUB_ID=1020633

§2-4a, memorandum heading:

1. **Office symbol** (writer’s office), e.g. `ISES–RM`.
2. **ARIMS record number** in parentheses after the symbol:
   `ISES–RM (25-50a)`. “Agencies will place the appropriate
   Army record number after the office symbol on memorandums.”
3. **Date**, same line, right margin, after signature.
4. **SUBJECT:** “Use only one subject and write the subject in
   10 words or less, if possible.”

§3-5d: “Record numbers are not used on letters.” The RN is a
memo/records mark, not a civilian-letter decoration.

So the Army letterhead already carries: who (office symbol),
which prescribed series (RN), when (date), what (one subject
line). A clerk does not need to invent a type. They read the
parenthetical.

### Navy / Marine Corps — SECNAV M-5216.5

SECNAV M-5216.5, *Department of the Navy Correspondence Manual*,
June 2015, Change 1 16 May 2018. Official copy opened:
https://www.navyband.navy.mil/documents/secnav-m52165-ch1.pdf
Policy wrapper: SECNAVINST 5216.7 (30 June 2015),
https://www.secnav.navy.mil/doni/Directives/05000%20General%20Management%20Security%20and%20Safety%20Services/05-200%20Management%20Program%20and%20Techniques%20Services/5216.7.pdf

Chapter 3, naming electronic folders:

> “When naming subdirectories or ‘folders,’ use the Standard
> Subject Identification Code (SSIC) (SECNAV M-5210.2 …) and
> any logical combination of alphanumeric characters …
> descriptive of the series.”

Identifying information “for each document may include the
office of origin, the SSIC, key words for retrieval, addressee
(if any), signature, originator, date, authorized disposition
…, and security classification (if applicable).”

Chapter 4, formal email: “Use standard DON correspondence
formats including an SSIC, serial number, date, and signature
authority.”

M-5210.2 §1-4 already ties this to the correspondence manual:
the action officer puts the SSIC on the document at creation.

---

## 6. Classification is orthogonal to subject filing

**Owning document:** DoDM 5200.01, Volume 1, *DoD Information
Security Program: Overview, Classification, and
Declassification*, 24 February 2012, Incorporating Change 3,
17 January 2025.
https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dodm/520001m_vol1.pdf

Volume 1’s purpose is “the designation, marking, protection,
and dissemination of controlled unclassified information (CUI)
and classified information.” It is the Confidential / Secret /
Top Secret (and CUI) program. It is **not** a subject file plan.
§9: “this Manual provide[s] the only authority for applying
security classification to information within the Department
of Defense” (except Atomic Energy Act material). Classification
answers “how tightly is this protected,” not “which functional
series is it.”

The records manuals keep the two axes apart on purpose:

- Navy M-5210.2 §1-6: the date / number / alpha arrangements
  “may also be used for all classified records.” §1-7: file
  classified and unclassified in **separate containers** (with
  narrow case-file exceptions). Same SSIC, different drawer.
- Army DA Pam 25-403 §5-4: classified and unclassified in
  separate containers except when a case needs both; mark the
  folder with the **highest** classification. The RN is
  unchanged.
- Air Force AFI 33-322 ¶3.3.1: inventory **titles must not
  contain** classification. Classification goes on the media
  label (¶4.6.5.1), not the browse name.
- OSD Primer Figure 1: “Records Classification” is its own
  file-plan column, next to File Number. §4.1.h: retrieve
  “regardless of media, location, classification, or format.”

**Do not** make Secret / TS / CUI a Burling main type. That
would confuse a security marking with a subject folder. A
Secret logistics memo is still `4000`. It just lives in a
different container.

---

## 7. DoD issuances numbering — a related official taxonomy

**Owning document:** DoWI 5025.01, *DoW Issuances Program*,
20 January 2026.
https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dodi/502501p.pdf

§4: the public issuances website “will contain … (4) An
explanation of the issuance numbering system.” The explanation
itself is listed on the supporting-documents page as “DoW
Issuance Numbering System” and is marked **CAC / PKI** — not
opened here. Do not invent a full 1000/2000/3000 DoD-issuance
series list.

What *is* on the public record:

- FAQ (https://www.esd.whs.mil/Directives/faq/): the records
  standard is `.##` (e.g. `5000.01` not `5000.1`). An `E`
  suffix means the issuance names a DoD Executive Agent.
- The public DoDI catalog
  (https://www.esd.whs.mil/Directives/issuances/dodi/) is
  sorted by issuance number. Observable clusters on that
  official table, without inventing titles: `1000.xx`
  identity/personnel-admin, `5000.xx` acquisition/management,
  `5200.xx` information security, `7000.xx` finance, `8000.xx`
  IT. Treat those as catalog observations, not a published
  series bible.
- Navy / Marine **directives** on DONI are physically filed
  in SSIC folders (`03000` Naval Operations and Readiness,
  `05000` General Management, Security and Safety). The
  issuance number *is* the SSIC. Example:
  https://www.secnav.navy.mil/doni/Directives/05000%20General%20Management%20Security%20and%20Safety%20Services/05-200%20Management%20Program%20and%20Techniques%20Services/5210.8F.pdf

For Burling: DoD issuance numbers are another **prescribed
functional series**, same instinct as SSIC. They are not a
discovered topic model. Do not copy a series table you cannot
open.

---

## 8. Federal floor (why every service has a plan)

36 CFR 1220.18 (NARA): a **series** is “file units or documents
arranged according to a filing or classification system or kept
together because they relate to a particular subject or
function.” A **recordkeeping system** “captures, organizes, and
categorizes records to facilitate their preservation, retrieval,
use, and disposition.”
https://www.ecfr.gov/current/title-36/chapter-XII/subchapter-B/part-1220/section-1220.18

36 CFR 1222.28: each program must set series-level
requirements including “arrangement of each series and the
records within the series.”
https://www.ecfr.gov/current/title-36/chapter-XII/subchapter-B/part-1222/subpart-B/section-1222.28

SECNAV M-5210.2 Part II §1 says SSICs plus schedule numbers
are how DON meets 36 CFR 1222.28. The file plan is the
statutory mechanism, not a product preference.

---

## Steal list (product, not clerk)

1. **Prescribe the top level.** ~13 functional heads (Navy) or
   a small series list (OSD 100/200/…). Do not cluster a dump
   into “Usenet 1993.”
2. **One primary home.** Closest subject code at creation.
   Cross-ref if a second action needs a pointer. Do not
   duplicate the file as two roots.
3. **Author assigns, clerk files.** The code is on the
   letterhead / subject line. Burling’s analog: read the
   subject (and any existing office symbol / form number) and
   drop it in the numbered folder.
4. **Year is a cutoff, not a type.** Navy date arrangement,
   Army “RN and title and current year,” Air Force FY/CY
   subfolders, OSD dummy folder + year tabs.
5. **Office symbol is originator metadata**, not a browse
   head. Same record type from two offices still shares the
   RN / SSIC / table-and-rule.
6. **Classification is a column / a drawer.** Secret logistics
   is still logistics.
7. **Unidentified ≠ new type.** Army: send it to the records
   manager. Air Force: 48-hour e-file box. OSD: propose a
   new file number to RIM / NARA. Burling’s analog: an
   `Unmapped` bin with a human, not a model-invented head.
8. **File plan = checked-out rows of a schedule.** DoDM 8180.01
   and every service manual agree. Burling can steal the
   *shape* (main type → subtype → folder) without stealing
   the retention legal machinery.

---

## Source list

### Opened and cited (official PDF or first-party HTML)

| Document | Date / version | URL |
|---|---|---|
| SECNAV M-5210.2 SSIC Manual | Aug 2018 | https://www.secnav.navy.mil/doni/SECNAV%20Manuals1/5210.2.pdf |
| SECNAV M-5210.1 landing (DON CIO HTML) | Sep 2019 | https://www.doncio.navy.mil/contentview.aspx?id=707 |
| SECNAVINST 5210.8F DON Records Management Program | 26 Mar 2019 | https://www.secnav.navy.mil/doni/Directives/05000%20General%20Management%20Security%20and%20Safety%20Services/05-200%20Management%20Program%20and%20Techniques%20Services/5210.8F.pdf |
| SECNAV M-5216.5 CH-1 Correspondence Manual | Jun 2015 / CH-1 16 May 2018 | https://www.navyband.navy.mil/documents/secnav-m52165-ch1.pdf |
| SECNAVINST 5216.7 Correspondence Management Program | 30 Jun 2015 | https://www.secnav.navy.mil/doni/Directives/05000%20General%20Management%20Security%20and%20Safety%20Services/05-200%20Management%20Program%20and%20Techniques%20Services/5216.7.pdf |
| AR 25-400-2 Army Records Management Program | 18 Oct 2022 | https://armypubs.army.mil/epubs/DR_pubs/DR_a/ARN38446-AR_25-400-2-001-WEB-2.pdf |
| DA Pam 25-403 Army Guide to Recordkeeping | 10 Nov 2022 | https://armypubs.army.mil/epubs/DR_pubs/DR_a/ARN38438-PAM_25-403-002-WEB-3.pdf |
| AR 25-50 Preparing and Managing Correspondence | 10 Oct 2020 (admin revs through 2024) | https://armypubs.army.mil/epubs/DR_pubs/DR_a/ARN42124-AR_25-50-007-WEB-13.pdf |
| AFI 33-322 + DAFGM 2025-01 | 23 Mar 2020 / GM 26 Jun 2025 | https://static.e-publishing.af.mil/production/1/saf_cn/publication/afi33-322/afi33-322.pdf |
| DoDM 8180.01 IT Planning for Electronic Records Management | 4 Aug 2023 | https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dodm/818001m.PDF |
| DTM-22-001 DoD Standards for RM Capabilities | 3 Mar 2022, Ch. 2 | https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dtm/DTM-22-001.PDF |
| OSD RIM Primer | 12 Dec 2023 | https://www.esd.whs.mil/Portals/54/Documents/OSD%20RIM%20PRIMER_12%20Dec%202023_(F).pdf |
| DoDM 5200.01 Vol. 1 Information Security Program | 24 Feb 2012, Ch. 3 17 Jan 2025 | https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dodm/520001m_vol1.pdf |
| DoWI 5025.01 DoW Issuances Program | 20 Jan 2026 | https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dodi/502501p.pdf |
| NARA JS/CCMD inspection (quotes DoDI 5015.02) | Apr 2020 | https://www.archives.gov/files/records-mgmt/pdf/dod-js-ccmds-inspection-report-2020.pdf |
| NARA Bulletin 2008-07 (endorsed 5015.2-STD v3) | 10 Sep 2008 | https://www.archives.gov/records-mgmt/bulletins/2008/2008-07.html |
| NARA Bulletin 2022-01 (revoked that endorsement) | 2022 | https://www.archives.gov/records-mgmt/bulletins/2022/2022-01 |
| 36 CFR 1220.18 / 1222.28 | current eCFR | https://www.ecfr.gov/current/title-36/chapter-XII/subchapter-B/part-1220/section-1220.18 |
| JITC RMA pages (5015.02-STD status) | updated 2 Jul 2025 | https://jitc.fhu.disa.mil/projects/rma/index.aspx |
| RMDA ARIMS Generic SOP template | undated template | https://www.rmda.army.mil/records-management/docs/ARIMS_Generic_SOP.pdf |

### Could not open (cited only via landing page or another official doc)

| Document | What happened | Fallback used |
|---|---|---|
| SECNAV M-5210.1 full PDF (2019) | DONI manuals index and `5210.1.pdf` timed out / no public file at the expected manuals path | DON CIO HTML summary; M-5210.2’s description of M-5210.1 as the disposition-schedule companion |
| DoDI 5015.02 PDF (`501502p.pdf`) | Fetch timed out | NARA 2020 inspection quote; DoDM 8180.01 / DTM-22-001 as implementers; https://www.esd.whs.mil/RIM/ listing |
| DoD 5015.02-STD April 2007 PDF | JITC `p50152stdapr07.pdf` timed out | JITC official HTML description; cancellation line in DoDM 8180.01; NARA bulletins 2008-07 and 2022-01 |
| DoW Issuance Numbering System (the actual series table) | Listed on esd.whs.mil supporting-documents page as CAC/PKI | DoWI 5025.01 §4 (system exists); FAQ on `.##`; no invented series list |
| MCO 5210.11 (Marine Corps electronic file plan) | Not fetched | M-5210.2 points Marines there; Navy clerk chapter “does not apply to the Marine Corps” |
| Full DONI copy of SECNAV M-5216.5 | `5216.5 (2015).pdf` on doni timed out | Official Navy Band host of the same manual + CH-1 |

### Not used as authority

Wikipedia, blogs, tpub.com, Scribd, Military Review (MARKS
history), FAS copies of superseded AFMAN 33-363. AFMAN 33-363
is superseded by AFI 33-322; the current AFI’s “inventory of
records” + table-and-rule language is what is cited.
