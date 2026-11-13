# SAVANNAH: STVR & CAD STUDY

## Listings, Capacity, & Calls

[Open the interactive map](https://michaelwoodc.github.io/savannah-stvr-cad-study/)

An interactive study of licensed Savannah short-term rental parcels, local listing capacities and amenity evidence, and normalized recorded-address calls for service. The site defaults to citizen-initiated calls. Map filters, comparisons, and downloads are available in the sidebar; the methodology is in [REPORT.md](REPORT.md).

[Listing size vs. calls line plots](size_plots/index.html) compare bedrooms and advertised guest capacity with citizen-initiated property, immediate residential-neighbor, and combined annual calls. Downloadable PNG/SVG plots, grouped data, parcel data, and normalized residential call records are included. Rebuild with `python plot_listing_size.py` (requires pandas and matplotlib). Each parcel counts once, using its largest known listing size; see the plot page for interpretation.

Open `index.html` locally or serve this directory with a static web server. The application and Leaflet assets are bundled; the optional OpenStreetMap basemap requires internet access. GitHub Pages serves `main` from the repository root.

The 59% booking-occupancy adjustment is an adjustable scenario, sourced in the app. It is not observed property-specific occupancy or proof that a call occurred during a booked stay. Advertised guest capacity is distinct from that booking assumption. Listing capacity flags and keywords are screening evidence, not findings of violations or incident responsibility. All property and neighbor associations use the documented parcel matching rules.

Tybee-location listings are excluded from Savannah listing analysis before permit matching. Excluded listing records remain clearly labeled in the linked audit. Hotel and commercial calls are excluded from the residential statistical comparisons. Raw local listing folders, unrelated county-map code, local backups, and unresolved call-assignment files are not part of this publication.

The repository contains the current standalone study and its linked data downloads, not the original ingestion workspace. Original local inputs are needed to regenerate the source study.

[AirDNA Savannah occupancy source](https://www.airdna.co/vacation-rental-data/app/us/georgia/savannah/overview). See `sources/` and the in-map attribution for municipal GIS and hotel sources. Leaflet's license is included with its assets. Original basemap attribution remains on the map.

Listing joins were revalidated against source-text permits and displayed-location contradictions on October 28, 2026. Folder tags are not match evidence. See `processed_data/listing_matches/source_match_audit.csv`, `folder_rename_log.csv`, and the correction note in REPORT.md.
