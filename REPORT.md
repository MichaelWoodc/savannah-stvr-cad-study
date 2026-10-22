# SAVANNAH: STVR & CAD STUDY

## Listings, Capacity, & Calls

[Open the map](index.html). This document describes the published application. The linked CSV exports document their own measure and denominator fields; older raw exports can use the all-retained-call basis rather than the current citizen-only default.

## Scope and records

- Savannah city limits intersected with the official local STVR overlay; unincorporated Chatham County is outside the study.
- 4,806 eligible residential parcels; 991 licensed residential parcels. License rows and units can share a tax parcel.
- Original fixed random sample of 991 nonlicensed residential parcels, without replacement, seed 20261021.
- Call exposure: 2024-09-21 through 2026-10-16, 756 days (2.069815 years).
- Citizen-initiated calls are the default; all-retained normalized calls are an explicit option. Recorded-address calls are not confirmed crimes, verified 911-origin records, or proof of an STVR's involvement.
- Only definitive normalized parcel matches enter residential call comparisons. Commercial properties, hotels and their calls are excluded. Excluded licensed parcels and hotels are absent from map layers. Nonlicensed nonhotel commercial neighbors can be explored separately.

## Averages and filters

A neighbor shares more than 0.1 m of parcel boundary, with no overlapping interior. Corner-only contacts and across-road proximity do not qualify.

House only = direct call memberships / focal parcel count / exposure years.

House + neighbors = combined direct and residential-neighbor call memberships / (focal parcel count + residential-neighbor parcel memberships) / exposure years.

Neighbors only = neighbor call memberships / residential-neighbor parcel memberships / exposure years.

These are pooled per-parcel rates. Shared neighbors can count in multiple focal neighborhoods. Zero-call parcels stay in denominators; parcels without neighbors add no neighbor memberships. Call numbers are deduplicated inside each focal neighborhood. Cohort membership totals are not regional unique-call totals.

All residential shows the full-population direct rate rather than repeated neighborhood rows. The random reference stays fixed under listing and category filters. The selected initiation measure applies to every cohort. STVR rows respond to listing, threshold and category filters. The unfiltered row ignores those filters, but retains the chosen initiation measure and occupancy assumption.

Default citizen-only display, with 59% STVR booking occupancy:

| Measure | All residential/calendar year | Random/calendar year | STVR/estimated occupied year |
|---|---:|---:|---:|
| House only | 0.559 | 0.565 | 0.573 |
| House + neighbors | Full-population reference above | 0.495 | 0.537 |
| Neighbors only | Full-population reference above | 0.465 | 0.521 |

[Default rate export](overall_comparison_default_59_percent.csv).

## Booking occupancy assumption

Default 59%, adjustable from 1% to 100%, sourced to [AirDNA Savannah](https://www.airdna.co/vacation-rental-data/app/us/georgia/savannah/overview), verified October 21, 2026; the source page was updated October 20, 2026. AirDNA measures booked nights divided by available nights. The scenario assumes year-round availability and applies a citywide snapshot across the study period. It does not establish property-specific or historical occupancy, or when calls occurred. STVR scenario rates divide calendar-year rates by the chosen occupancy fraction. Raw call counts and map colors stay on a calendar-year basis. Advertised guest capacity is separate from booking occupancy.

## Listing screening and location safeguards

4,372 local details files were screened; 925 listing rows match 561 eligible licensed residential parcels after location exclusions. 167 listings on 125 parcels advertise above the matched license allowance. These are screening flags, not proven violations or observed occupancy.

Tybee-location rentals are excluded before Savannah permit matching, because permit identifiers can overlap across jurisdictions. The location check uses the official Tybee Island polygon with a 500 m coastal/privacy buffer for approximate displayed Airbnb coordinates; explicit Tybee location labels are used when coordinates are absent. Host company names and incidental mentions of Tybee are not exclusion rules. [Excluded Tybee listing audit](excluded_tybee_listings.csv) preserves rejected candidate joins without making them active Savannah matches.

Advertised capacity uses the existing explicit guest field or compact listing-facts line. A single detected certificate uses its approved allowance; multiple matched certificates use the sum of known allowances as documented in the audit. Additional same-address licenses are shown separately, italicized when not detected in that listing, and are not silently added to its allowance. Bedroom counts come from explicit local bedroom headers. Unknown values are excluded only when the corresponding size minimum is active. Minimum-bedroom and advertised-guest filters include compliant larger listings.

Generic party/celebration word matching is removed. Amenity evidence is context-labeled; restrictions such as no parties, unavailable facilities, nearby attractions and on-site facilities are distinct. Quotations, rule definitions and folder fingerprints are available in the linked listing exports. Match quality, separate units, historical license status and listing changes can limit interpretation.

## Map controls

At zoom 18+, circles show direct property call counts; zero-call circles are omitted. Licensed parcels have thick navy outlines and hatching. A red second hatch direction marks an advertised-capacity overage or on-site amenity evidence. Red pulsing outlines mark direct calls/year at least three times the full residential average under the selected category and initiation filters. These are visual screening cues, not incident attribution. Reduced-motion preferences disable pulses.

Category checkboxes combine selections with OR; no selection means all categories. Selecting a category hides properties with no matching direct calls from the map and ranked results, while zero-call cases remain in statistical denominators. Property cards start with all sections collapsed. Clicking a section fills the card while retaining the address at its top. Matched Airbnb links are shown near the top; missing matches are labeled explicitly.

The ranked list defaults to house + neighbors. Its default-on above-average option compares the selected occupancy-adjusted per-parcel rate against the corresponding random reference; it affects the ranked list, not the statistical cohort. Listing rows sharing a parcel repeat parcel call totals and must not be summed as distinct properties.

## Saved state and source attribution

Saved state is opt-in. With consent, cookies remember filters, map area, panel visibility and the open property state; file-mode browsing uses local storage as a fallback. Clear all filters restores defaults and keeps the map area. Cookie preferences can withdraw consent and remove saved state. No analytics service is included.

Official municipal/overlay GIS and hotel source snapshots are in `sources/`. The study uses the local license workbook and normalized call records represented in the published exports; the ingestion workspace and raw listing folders are not included. Original source dates and exclusions are retained in the license, parcel and listing audits. Leaflet and OpenStreetMap attribution remain in the app.
