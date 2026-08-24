# Rich tags (Pass A)

Free-form multi-label tags before Pass B stitch. See `docs/tag-then-stitch.md`.

**Documents tagged:** 18
**Needs review:** 0
**Unique tags:** 164
**Avg tags/doc:** 9.1

## Top tags

| Tag | Docs |
|---|---|
| `drip-irrigation` | 1 |
| `orchard-maintenance` | 1 |
| `watering-schedule` | 1 |
| `even-days` | 1 |
| `dawn-watering` | 1 |
| `filter-flush` | 1 |
| `fruit-set-observation` | 1 |
| `windbreak-management` | 1 |
| `seed-catalog` | 1 |
| `open-pollinated` | 1 |
| `tomato` | 1 |
| `Amish-Paste` | 1 |
| `hybrid-sweetcorn` | 1 |
| `cover-crop-rye` | 1 |
| `planting-log` | 1 |
| `germination-rate` | 1 |
| `order-notes` | 1 |
| `agricultural-planning` | 1 |
| `soil-test` | 1 |
| `agricultural-soil-test` | 1 |
| `lime-application` | 1 |
| `cover-crop` | 1 |
| `clover` | 1 |
| `maize` | 1 |
| `east-field` | 1 |
| `south-strip` | 1 |
| `organic-matter` | 1 |
| `phosphorus-low` | 1 |
| `potassium-adequate` | 1 |
| `spring-soil-test` | 1 |
| `air-quality-brief` | 1 |
| `pm25` | 1 |
| `inversion-morning` | 1 |
| `valley-floor-advisory` | 1 |
| `wood-stove-curtailment` | 1 |
| `stage-1-alert` | 1 |
| `environmental-monitoring` | 1 |
| `air-pollution` | 1 |
| `municipal-recycling` | 1 |
| `contamination-audit` | 1 |

## By document

### `ag-irrigation-schedule.txt`

- **tags:** `drip-irrigation`, `orchard-maintenance`, `watering-schedule`, `even-days`, `dawn-watering`, `filter-flush`, `fruit-set-observation`, `windbreak-management`
- **entities:** `orchard-block-B`, `sand-filter`
- **artifacts:** `maintenance-schedule`, `irrigation-log`
- **summary:** A maintenance directive for orchard block B specifying a drip irrigation schedule that runs two hours before dawn on even calendar days, noting a prior sand filter clog in June and observing uneven moisture conditions with the windbreak side being drier.

### `ag-seed-catalog-notes.txt`

- **tags:** `seed-catalog`, `open-pollinated`, `tomato`, `Amish-Paste`, `hybrid-sweetcorn`, `cover-crop-rye`, `planting-log`, `germination-rate`, `order-notes`, `agricultural-planning`
- **entities:** `Amish Paste`, `cover-crop rye`
- **artifacts:** `seed-catalog-notes`, `planting-log`, `order-tracker`
- **summary:** A farmer or gardener recorded germination results and ordering reminders from seed packets. The notes track a successful open-pollinated tomato trial, a hybrid sweetcorn packet sold out until March, and a restock order for cover-crop rye to avoid last year's planting delays.

### `ag-soil-test.txt`

- **tags:** `soil-test`, `agricultural-soil-test`, `lime-application`, `cover-crop`, `clover`, `maize`, `east-field`, `south-strip`, `organic-matter`, `phosphorus-low`, `potassium-adequate`, `spring-soil-test`
- **entities:** `east field`, `south strip`
- **artifacts:** `soil-test-report`, `agricultural-notes`, `field-notes`
- **summary:** A brief spring soil test summary for an east field, reporting pH 6.2, low phosphorus, adequate potassium, and recommending lime application ahead of maize planting. The south strip is noted to retain last year's clover as a cover crop.

### `env-air-quality-brief.txt`

- **tags:** `air-quality-brief`, `pm25`, `inversion-morning`, `valley-floor-advisory`, `wood-stove-curtailment`, `stage-1-alert`, `environmental-monitoring`, `air-pollution`
- **entities:** `valley-floor`
- **artifacts:** `brief`, `advisory`, `environmental-report`
- **summary:** A morning air quality brief reports that PM2.5 peaked at 38 µg/m³ between 07:00 and 08:00, affecting the valley floor only. It notes that wood-stove curtailment is currently voluntary but would become mandatory under a Stage 1 alert.

### `env-recycling-audit.txt`

- **tags:** `municipal-recycling`, `contamination-audit`, `blue-bin-recycling`, `food-soiled-cardboard`, `plastic-bags-recycling`, `mrf-rejection-threshold`, `sticker-campaign`, `pilot-neighborhood-outreach`
- **entities:** `MRF`
- **artifacts:** `audit-report`, `campaign-material`, `data-summary`
- **summary:** A municipal recycling audit report finds 18 percent contamination in blue bins, primarily from food-soiled cardboard and plastic bags, noting the MRF will reject loads exceeding 20 percent contamination. It documents a sticker campaign on pizza boxes that reduced contamination by two percentage points in a pilot neighborhood.

### `env-wetland-survey.txt`

- **tags:** `wetland-bird-survey`, `oxbow-marsh`, `bird-observation`, `wetland-ecology`, `species-count`, `habitat-management`, `nesting-season`, `water-level`, `ditch-cleanout`, `wildlife-survey`
- **entities:** `oxbow marsh`, `least bittern`
- **artifacts:** `field-survey-notes`, `observation-log`, `environmental-assessment`
- **summary:** A brief field note documenting an 18-species wetland bird survey at an oxbow marsh, noting a least bittern heard but not seen, elevated water levels from recent rain, and a recommendation to postpone a planned ditch cleanout to protect nesting activity.

### `finance-budget-worksheet.txt`

- **tags:** `household-budget`, `monthly-budget-worksheet`, `personal-finance`, `budget-tracking`, `expense-management`, `rent`, `groceries`, `transit`, `car-insurance-sinking-fund`, `budget-adjustment`
- **artifacts:** `worksheet`, `budget-sheet`, `finance-tracker`
- **summary:** A personal household monthly budget worksheet tracking fixed expenses (rent, transit, car insurance sinking fund) and variable costs (groceries, streaming), with notes on last month's overspending and adjustments to streaming bundle instead of groceries.

### `finance-savings-goal.txt`

- **tags:** `emergency-fund`, `savings-goal`, `automatic-transfer`, `budget-planning`, `financial-management`, `essential-expenses`, `travel-envelope`, `monthly-budget`
- **entities:** `automatic-transfer-schedule`
- **artifacts:** `financial-goal-tracker`, `budget-notes`
- **summary:** This document outlines a personal emergency-fund savings goal targeting three months of essential bills, currently at $4,200. It establishes an automatic transfer of $150 on the 1st and 15th of each month and explicitly separates a travel envelope from the emergency fund to prevent accidental withdrawals for vacation spending.

### `finance-tax-checklist.txt`

- **tags:** `tax-checklist`, `year-end-tax`, `w-2-lookalikes`, `1098-mortgage-interest`, `charitable-receipts`, `estimated-payments`, `single-filing-status`, `practice-list`, `fictional-tax`, `tax-preparation`
- **entities:** `W-2`, `1098`, `IRS`
- **artifacts:** `checklist`, `tax-document-guide`, `practice-material`
- **summary:** A fictional practice checklist for year-end tax preparation that guides users to gather W-2 forms, mortgage interest statements (1098), and charitable receipts over $250, noting estimated tax payments made in June and September and identifying the filer as single. It is explicitly labeled as a practice list and not official tax advice.

### `health-clinic-hours.txt`

- **tags:** `clinic-hours`, `walk-in-clinic`, `flu-shot-clinic`, `well-child-visits`, `immunization-clinic`, `health-center-hours`, `after-hours-clinic`, `community-health-access`
- **entities:** `flu-shot-clinic`, `well-child-visits`
- **artifacts:** `clinic-schedule`, `health-announcement`, `public-health-notice`
- **summary:** This document lists the walk-in hours for a community health clinic, specifying Tuesday and Thursday evenings and noting that Saturday well-child slots are full through the end of the month. It also informs visitors that flu shots are available in a side room and that an insurance card should be brought if applicable.

### `health-heat-advisory.txt`

- **tags:** `heat-advisory`, `outdoor-workers`, `heat-index`, `mandatory-breaks`, `water-requirement`, `roof-work-cancellation`, `extreme-heat`, `worker-safety`
- **entities:** `heat-index`, `water`
- **artifacts:** `advisory`, `safety-guideline`
- **summary:** A heat advisory mandating 15-minute shade breaks hourly and one liter of water per person per hour when the heat index exceeds 103°F, with a directive to cancel non-essential roof work after 14:00 to protect outdoor workers from extreme heat.

### `health-vaccine-faq.txt`

- **tags:** `health-vaccine-faq`, `school-health`, `immunization-record`, `measles-mumps-rubella`, `county-board-policy`, `philosophical-exemption`, `two-dose-schedule`, `sixth-grade-entry`
- **entities:** `county-board`
- **artifacts:** `faq`, `health-faq`
- **summary:** A frequently asked questions document outlining school vaccination requirements for sixth grade entry, specifically addressing MMR dose requirements, the limited acceptance of measles history as a substitute for the first dose, and the county board's policy prohibiting philosophical exemptions.

### `sports-league-standings.txt`

- **tags:** `basketball-standings`, `harbor-five`, `week-four-protest`, `makeup-games-elementary-gym`, `scorebook-required`, `travel-call-dispute`, `recreational-basketball`, `local-league-results`
- **entities:** `harbor-five`
- **artifacts:** `standings-report`, `game-schedule-update`
- **summary:** A brief update on Tuesday night basketball league standings, noting that Harbor Five leads with a 7–1 record and that a protest from week four regarding a late travel call was denied. It also specifies that any makeup games will be played at the elementary gym and that participants should bring their own scorebooks.

### `sports-pool-schedule.txt`

- **tags:** `indoor-pool`, `schedule`, `november`, `lap-swim`, `lessons`, `dive-well`, `filter-maintenance`, `adult-fitness`, `sports-facility`, `pool-operations`
- **entities:** `indoor-pool`, `dive-well`
- **artifacts:** `schedule`, `operational-plan`
- **summary:** A November schedule for an indoor pool outlining lap swim hours, lane assignments for lessons, and maintenance closures for the dive well, with spectator areas kept clear during adult fitness times.

### `sports-trail-race.txt`

- **tags:** `trail-race`, `trail-race-volunteer-brief`, `aid-station`, `aid-station-2`, `sweep-crew`, `fire-road-shared-use`, `horse-share`, `mile-8-4`, `volunteer-guidance`, `running-event`
- **entities:** `aid station 2`, `ridge junction`
- **artifacts:** `volunteer-brief`, `event-guidance`, `checklist`
- **summary:** A briefing document for trail race volunteers outlining aid station placement at the ridge junction (mile 8.4), requirements for runners to carry their own bottles, sweep crew timing relative to starters, and shared use of the fire road with horses before noon.

### `transport-bike-lane-memo.txt`

- **tags:** `bike-lane`, `protected-bike-lane`, `cycle-track`, `maple-avenue`, `traffic-signal`, `leading-interval`, `counts-data`, `weekday-ridership`, `parking-lane-conversion`, `corridor-improvement`
- **entities:** `Maple Avenue`, `4th Street`
- **artifacts:** `memo`, `design-memo`, `transportation-planning-doc`, `engineering-memo`
- **summary:** A planning memo outlining the conversion of a parking lane on Maple Avenue into a two-way protected bike lane (cycle track), noting the need for signal timing adjustments at 4th Street to prevent conflicts with turning trucks and citing count data showing 1,400 weekday riders.

### `transport-harbor-pilot.txt`

- **tags:** `harbor-pilot`, `container-ship`, `port-operations`, `tug-availability`, `estuary-fog`, `berth-delay`, `licensed-pilot`, `buoy-12`
- **entities:** `port-operations-board`, `buoy-12`
- **artifacts:** `notice`, `maritime-safety-bulletin`
- **summary:** A port authority notice informing that container ships exceeding 200 meters in length are required to board a licensed harbor pilot at buoy 12. The document records that fog conditions in the estuary during March caused delays at three berths, and clarifies that tug availability is communicated via the port operations board rather than radio.

### `transport-rail-timetable.txt`

- **tags:** `rail-timetable`, `weekday-peak`, `north-line`, `express-trains`, `suburban-stops`, `weekend-engineering`, `bridge-blockade`, `replacement-buses`, `freight-yard`, `service-road`
- **entities:** `city rail`, `north line`, `river bridge`, `freight yard`
- **artifacts:** `timetable`, `schedule`
- **summary:** A weekday peak-hour rail timetable for the city's north line, noting express trains that skip suburban stops and a scheduled weekend engineering blockade on the river bridge that will require replacement bus services via a service road beside the freight yard.
