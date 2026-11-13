# Corrected size and party-feature associations

484 source-validated matched parcels, including zeros. 66 direct noise/loud-party/disturbance calls; only 472 parcels have known advertised capacity for modeling.

These are recorded-address citizen calls, not confirmed crimes, guest responsibility or verified 911 origin. Medical and other unrelated categories are not counted in this primary outcome. Direct and combined neighborhood results are separate. The main available period is January 1, 2024-October 16, 2026; 59% adjusts only focal rental exposure, not neighbors. The later source remains a retained/filtered extract.

## Top ten size plots

[Open the copied size-trend plots](top_10_size_trends/) or [the interactive source-property explorer](../top_correlations/index.html). These rank supported exact-size group-mean rises, not causal effects or individual-property explained variance. All ten selected series are non-owner-occupied.

| Rank | Size measure | Call type | Cohort | Parcels | Calls | Plot |
|---:|---|---|---|---:|---:|---|
| 1 | Advertised bedrooms | Noise complaints | All covered licenses with known size | 411 | 23 | [View](top_10_size_trends/01__current_direct__every_licensed_address__bedrooms__exact__noise_complaints.png) |
| 2 | Advertised guests | Noise complaints | All covered licenses with known size | 411 | 23 | [View](top_10_size_trends/02__current_direct__every_licensed_address__guests__exact__noise_complaints.png) |
| 3 | Licensed bedrooms | Disturbance / nuisance | Matched Airbnb | 423 | 15 | [View](top_10_size_trends/03__current_direct__matched_airbnb__licensed_bedrooms__exact__disturbance_nuisance.png) |
| 4 | Licensed bedrooms | Noise complaints | Matched Airbnb | 423 | 23 | [View](top_10_size_trends/04__current_direct__matched_airbnb__licensed_bedrooms__exact__noise_complaints.png) |
| 5 | Licensed bedrooms | Disturbance / nuisance | All covered licenses with known size | 864 | 34 | [View](top_10_size_trends/05__current_direct__every_licensed_address__licensed_bedrooms__exact__disturbance_nuisance.png) |
| 6 | Advertised guests | Disturbance / nuisance | All covered licenses with known size | 411 | 15 | [View](top_10_size_trends/06__current_direct__every_licensed_address__guests__exact__disturbance_nuisance.png) |
| 7 | Approved guest capacity | Disturbance / nuisance | Matched Airbnb | 423 | 15 | [View](top_10_size_trends/07__current_direct__matched_airbnb__approved_guests__exact__disturbance_nuisance.png) |
| 8 | Licensed bedrooms | Loud party | All covered licenses with known size | 864 | 36 | [View](top_10_size_trends/08__current_direct__every_licensed_address__licensed_bedrooms__exact__loud_party.png) |
| 9 | Licensed bedrooms | Noise complaints | All covered licenses with known size | 864 | 44 | [View](top_10_size_trends/09__current_direct__every_licensed_address__licensed_bedrooms__exact__noise_complaints.png) |
| 10 | Approved guest capacity | Noise complaints | Matched Airbnb | 423 | 23 | [View](top_10_size_trends/10__current_direct__matched_airbnb__approved_guests__exact__noise_complaints.png) |

## Top ten combination review candidates

Search considered 2359 descriptions, collapsed to 840 distinct property groups. 547 direct/neighborhood tests passed minimum support and were fitted. 0 increases passed the 5% false-discovery screen. All ten below remain exploratory review candidates; higher joint rates do not establish extra synergy.

| Rank | Condition | Properties | Calls | Adjusted ratio | Clustered 95% interval | FDR q |
|---:|---|---:|---:|---:|---:|---:|
| 1 | [Guest capacity 8+](plots/01__candidate.png) | 112 | 38 | 6.82 | 1.97-23.58 | 0.134 |
| 2 | [Outdoor space + 8+ advertised guests](plots/02__candidate.png) | 82 | 34 | 5.97 | 1.94-18.36 | 0.134 |
| 3 | [Grill / BBQ + Hot tub / Jacuzzi](plots/03__candidate.png) | 16 | 10 | 4.61 | 1.85-11.48 | 0.134 |
| 4 | [Grill / BBQ + Hot tub / Jacuzzi](plots/04__candidate.png) | 17 | 10 | 4.40 | 1.78-10.88 | 0.134 |
| 5 | [Outdoor dining + Swimming pool](plots/05__candidate.png) | 22 | 13 | 4.68 | 1.66-13.20 | 0.134 |
| 6 | [Patio / deck / balcony / porch + Swimming pool + 8+ advertised guests](plots/06__candidate.png) | 22 | 14 | 3.30 | 1.63-6.69 | 0.134 |
| 7 | [Hot tub / Jacuzzi + 6+ advertised guests](plots/07__candidate.png) | 17 | 11 | 3.77 | 1.55-9.14 | 0.134 |
| 8 | [Cocktails / spirits + Patio / deck / balcony / porch + 6+ advertised guests](plots/08__candidate.png) | 17 | 11 | 3.37 | 1.49-7.61 | 0.134 |
| 9 | [Patio / deck / balcony / porch + Swimming pool + 8+ advertised guests](plots/09__candidate.png) | 21 | 13 | 3.03 | 1.46-6.28 | 0.134 |
| 10 | [Cocktails / spirits + Yard / garden / courtyard + 6+ advertised guests](plots/10__candidate.png) | 24 | 12 | 3.11 | 1.46-6.61 | 0.134 |

[Property and Airbnb links behind each candidate](candidate_properties_and_calls.csv) · [All adjusted results](all_adjusted_combinations.csv) · [Unsupported/failed conditions](insufficient_support_or_failed.csv) · [Interaction support](pair_synergy_support.csv)

## Method and limits

Physical on-site evidence and positive description/party-language evidence are declared separate families. Each condition must occur in one listing; a capacity cutoff must apply to that same listing. Each parcel is counted once. Identical exposed-property groups are tested once, retaining their aliases. Broad party words are not physical amenities.

Each binary condition is tested with a Poisson model, controlling log(1 + advertised capacity), owner-occupied permit type and log(1 + license count), using an exposure offset. Combined-neighbor counts use the eligible neighbor count plus 0.59 focal rental. Uncertainty clusters connect neighborhoods sharing any parcel. Minimum support: 15 exposed and 15 comparison parcels, 8 events and 5 positive-call parcels on each side, and 8 exposed spatial clusters. Controls do not remove all location or reporting confounding.

Benjamini-Hochberg false-discovery correction includes every fitted unique condition across both scopes. Large searches can create impressive accidental ratios; do not rank by raw votes or take the top row as established fact. Pair interaction tests require adequate observations in all four presence/absence cells. Sparse combinations are flagged rather than forced.

This data set is small enough for CPU analysis. CUDA memory or overnight computation cannot repair sparse outcomes, missing coverage or uncertain source matches. Rebuild with `python -m processing.party_combination_analysis`.
