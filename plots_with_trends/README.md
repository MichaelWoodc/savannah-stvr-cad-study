# Individual citizen-only plots with trends

297 individual charts, each as PNG and SVG. Original plots/ is unchanged. Only citizen-initiated records are included; patrol/proactive-stop labels are excluded. No subplot sheets. Guest/bedroom/amenity-count axes use integer ticks; approved-capacity ticks are even numbers.

## Strongest supported upward associations

Ranking is exploratory: positive parcel-weighted slope in exact-size current full/matched cohorts, at least 30 parcels, 4 size levels, 10 category calls and group-mean R² >= 0.20. The middle-half size range must be nonzero. Rank uses fitted rise per one SD of size, divided by cohort mean rate, so bedrooms and guests are comparable. It does not establish causality or statistical significance. Overlapping minimum-cutoff curves and capacity-selected cohorts are plotted but excluded from this primary ranking. R² describes group means, not individual-property variance. Multiple comparisons are not corrected.

| Plot | Series | Parcels | Calls | Group R² | Fitted middle-half rise |
|---|---|---:|---:|---:|---:|
| [current_direct__every_licensed_address__bedrooms__exact__noise_complaints](current_direct__every_licensed_address__bedrooms__exact__noise_complaints.png) | Non-owner-occupied | 411 | 23 | 0.36 | 0.047 |
| [current_direct__every_licensed_address__guests__exact__noise_complaints](current_direct__every_licensed_address__guests__exact__noise_complaints.png) | Non-owner-occupied | 411 | 23 | 0.48 | 0.044 |
| [current_direct__matched_airbnb__licensed_bedrooms__exact__disturbance_nuisance](current_direct__matched_airbnb__licensed_bedrooms__exact__disturbance_nuisance.png) | Non-owner-occupied | 423 | 15 | 0.38 | 0.030 |
| [current_direct__matched_airbnb__licensed_bedrooms__exact__noise_complaints](current_direct__matched_airbnb__licensed_bedrooms__exact__noise_complaints.png) | Non-owner-occupied | 423 | 23 | 0.27 | 0.046 |
| [current_direct__every_licensed_address__licensed_bedrooms__exact__disturbance_nuisance](current_direct__every_licensed_address__licensed_bedrooms__exact__disturbance_nuisance.png) | Non-owner-occupied | 864 | 34 | 0.24 | 0.031 |
| [current_direct__every_licensed_address__guests__exact__disturbance_nuisance](current_direct__every_licensed_address__guests__exact__disturbance_nuisance.png) | Non-owner-occupied | 411 | 15 | 0.34 | 0.025 |
| [current_direct__matched_airbnb__approved_guests__exact__disturbance_nuisance](current_direct__matched_airbnb__approved_guests__exact__disturbance_nuisance.png) | Non-owner-occupied | 423 | 15 | 0.20 | 0.019 |
| [current_direct__every_licensed_address__licensed_bedrooms__exact__loud_party](current_direct__every_licensed_address__licensed_bedrooms__exact__loud_party.png) | Non-owner-occupied | 864 | 36 | 0.53 | 0.024 |
| [current_direct__every_licensed_address__licensed_bedrooms__exact__noise_complaints](current_direct__every_licensed_address__licensed_bedrooms__exact__noise_complaints.png) | Non-owner-occupied | 864 | 44 | 0.34 | 0.029 |
| [current_direct__matched_airbnb__approved_guests__exact__noise_complaints](current_direct__matched_airbnb__approved_guests__exact__noise_complaints.png) | Non-owner-occupied | 423 | 23 | 0.32 | 0.025 |
| [current_direct__matched_airbnb__licensed_bedrooms__exact__loud_party](current_direct__matched_airbnb__licensed_bedrooms__exact__loud_party.png) | Non-owner-occupied | 423 | 20 | 0.26 | 0.025 |
| [current_direct__every_licensed_address__licensed_bedrooms__exact__all_calls](current_direct__every_licensed_address__licensed_bedrooms__exact__all_calls.png) | Non-owner-occupied | 864 | 837 | 0.53 | 0.464 |
| [current_direct__every_licensed_address__approved_guests__exact__all_calls](current_direct__every_licensed_address__approved_guests__exact__all_calls.png) | Non-owner-occupied | 864 | 837 | 0.79 | 0.345 |
| [current_direct__every_licensed_address__approved_guests__exact__loud_party](current_direct__every_licensed_address__approved_guests__exact__loud_party.png) | Non-owner-occupied | 864 | 36 | 0.43 | 0.014 |
| [current_direct__every_licensed_address__approved_guests__exact__noise_complaints](current_direct__every_licensed_address__approved_guests__exact__noise_complaints.png) | Non-owner-occupied | 864 | 44 | 0.45 | 0.016 |

Copies of these plots are in strongest_increases/. Full results are in increasing_plot_rankings.csv and all_trend_fits.csv.

## Amenities and review priorities

Physical evidence count uses hot tub, pool, grill, fire pit, sound system, bar, outdoor dining, patio and yard. It is a broad screening score, not proof of party use. The count is the largest single-listing score on each parcel, not an inflated union across listings. General mentions and event/group language are separate. No captured evidence is not proof of absence.

Adjusted feature associations use exploratory Poisson models with robust covariance, controlling advertised guest capacity, owner-occupied type and license count. Each feature is fitted separately. Models require minimum support; sparse outcomes are flagged rather than forced. This is not a causal amenity effect and does not control all location confounding.

- [Highest noise/party/disturbance review priorities](review_priorities__noise_party_disturbance.png)
- [Highest overall-call review priorities](review_priorities__all_calls.png)
- [Property evidence, counts and listing URLs](property_amenity_call_audit.csv)
- [Size-adjusted amenity associations and support flags](size_adjusted_amenity_associations.csv)

Highest-call lists are review priorities, not findings of violations or guest involvement. The primary nuisance ranking combines noise, loud-party and disturbance categories over the full available span. Parking stays separate because its covered period is only January 1-September 20, 2024. Main span: January 1, 2024-October 16, 2026. 59% is a scenario, not observed property occupancy.

## Average lines

In the _with_averages folder, dotted colored lines show each selected series/cohort average. Exact-group averages weight each parcel once. For overlapping minimum-cutoff groups the first cutoff gives the cohort mean; overlapping groups are not averaged together. Where categories and denominators align, a separate dashed gray residential calendar-year reference is included. Legacy denominators are kept separate. Adjusted-rate-ratio forest plots use ratio 1 as the comparison reference, not a misleading raw-rate mean.

Rebuild: python -m processing.trend_analysis. All chart data, support limits and source hashes are included.

Individual adjusted-association plots retain their original log-scale filenames; `__linear` counterparts use whole-number ticks. On-site amenity count charts and factors have been removed. [Expanded individual-feature and invitation-keyword comparisons](../adjusted_association_plots/index.html).
