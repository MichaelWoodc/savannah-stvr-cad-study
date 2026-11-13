# Top 10 upward associations

Open [the interactive property explorer](index.html). This folder contains exactly ten plots in PNG and SVG, with the corresponding group CSVs. Plots include trends and averages; images are linked rather than embedded in the page.

The selection follows the existing exploratory ranking, removing duplicate series/data and duplicate plots. It ranks exact-size associations by fitted increase per one SD of size relative to mean rate, with parcel/event/size-level support limits. It is not a ranking by Pearson correlation, a causal effect, or a finding of violations. All ten currently involve non-owner-occupied properties. Some cohorts overlap.

Click a factor to inspect its exact source cohort, including zero-call parcels. Use size/search and calls-only filters to narrow the list. Each property expands to matching category call records and Airbnb evidence. Counts match the ranked plot, count each parcel once, and exclude patrol/proactive records. Rates use the fixed 59% scenario and the stated category period.

Rebuild with `python -m processing.top_correlations`.

- 1. [Advertised bedrooms / Noise complaints / Every covered licensed property](01__current_direct__every_licensed_address__bedrooms__exact__noise_complaints.png)
- 2. [Advertised guest capacity / Noise complaints / Every covered licensed property](02__current_direct__every_licensed_address__guests__exact__noise_complaints.png)
- 3. [Licensed bedrooms (parcel total) / Disturbance / nuisance / Matched Airbnb properties](03__current_direct__matched_airbnb__licensed_bedrooms__exact__disturbance_nuisance.png)
- 4. [Licensed bedrooms (parcel total) / Noise complaints / Matched Airbnb properties](04__current_direct__matched_airbnb__licensed_bedrooms__exact__noise_complaints.png)
- 5. [Licensed bedrooms (parcel total) / Disturbance / nuisance / Every covered licensed property](05__current_direct__every_licensed_address__licensed_bedrooms__exact__disturbance_nuisance.png)
- 6. [Advertised guest capacity / Disturbance / nuisance / Every covered licensed property](06__current_direct__every_licensed_address__guests__exact__disturbance_nuisance.png)
- 7. [Approved guest capacity (parcel total) / Disturbance / nuisance / Matched Airbnb properties](07__current_direct__matched_airbnb__approved_guests__exact__disturbance_nuisance.png)
- 8. [Licensed bedrooms (parcel total) / Loud party / Every covered licensed property](08__current_direct__every_licensed_address__licensed_bedrooms__exact__loud_party.png)
- 9. [Licensed bedrooms (parcel total) / Noise complaints / Every covered licensed property](09__current_direct__every_licensed_address__licensed_bedrooms__exact__noise_complaints.png)
- 10. [Approved guest capacity (parcel total) / Noise complaints / Matched Airbnb properties](10__current_direct__matched_airbnb__approved_guests__exact__noise_complaints.png)
