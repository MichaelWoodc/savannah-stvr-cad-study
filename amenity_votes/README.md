# Amenity vote analysis

Open index.html for live scoring. All citizen-only currently licensed, address-matched properties are included, with zero-call cases and touching residential neighbors inside the fixed call-coverage population. Corners and across-road parcels are not neighbors; saved commercial/hotel exclusions and the established geometry rules are retained.

A raw vote is one feature/focal-parcel/call-number membership. Repeated mentions or listings do not duplicate a feature's vote inside a focal neighborhood. A call can vote for several features and several overlapping rental neighborhoods. This is not causal attribution or a regional unique-call total. The ledger preserves every membership.

The live subtract-average checkbox scores observed minus expected calls, or annualized rate minus the residential reference. Below-average properties contribute negative values. A separate per-advertising-property checkbox prevents raw totals automatically favoring common features. Both scoring choices and their units are displayed explicitly.

Expected calls = residential category rate × category years × exposure properties. Exposure is the booking fraction for the rental, one calendar year per eligible neighbor, or their sum. The 59% scenario applies only to the focal rental; neighbors are not assumed to share its booking rate. Parking uses the entire supported early period and never treats missing later coverage as zero.

Feature tallies use the union of captured positive feature/party-language mentions across matched listings on the parcel, while both union and maximum-single-listing scores are retained. Physical on-site evidence is also available separately. Generic language and physical amenities remain labeled separately. Evidence absence is not verified amenity absence. Scores are associations, not proof an amenity produced a call.

The rough capacity × amenity-count equation is compared with fitted Poisson alternatives using held-out groups. Neighborhoods that share a parcel are kept in the same validation group. This reduces shared-neighbor leakage but does not remove all spatial/temporal confounding or establish causality. Full available dates are retained, with the stated parking coverage exception. Rebuild: python -m processing.amenity_votes.
