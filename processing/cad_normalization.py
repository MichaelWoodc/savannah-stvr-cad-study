"""CAD-specific address classification without invented locality or parcel attribution."""
import re
from processing.address_normalization import clean, normalize_address

VERSION = '1.0.0'

def normalize_cad_address(address):
    text = clean(address)
    result = normalize_address(address)
    # CAD commonly records a street line only. Missing locality is metadata, not a parse error.
    flags = [x for x in result['review_reasons'].split('; ') if x and x != 'unparsed_or_missing_city_state_zip']
    kind = 'street_address'
    if not text:
        kind = 'missing'
    elif re.search(r'\s/\s|\s&\s|\sAND\s|\sAT\s|\s@\s', text) or ('/' in text and not re.search(r'\b\d+/\d+\b', text)):
        kind = 'intersection_or_location_description'
    elif re.search(r'\b(?:BLK|BLOCK)\b', text):
        kind = 'block_location'
    elif not result['house_number']:
        kind = 'street_or_landmark'
    elif re.fullmatch(r'\d+[A-Z]?-\d+[A-Z]?', result['house_number']):
        kind = 'house_number_range_or_hyphenated_number'
    if kind != 'street_address':
        flags.append(kind)
    result['address_kind'] = kind
    result['locality_present'] = bool(result['city'])
    result['review_reasons'] = '; '.join(dict.fromkeys(flags))
    result['review_required'] = bool(flags)
    result['street_building_candidate_key'] = result['normalized_building_address'] if not flags else ''
    result['street_unit_candidate_key'] = result['normalized_delivery_address'] if not flags else ''
    # Full keys require supplied locality; street-only keys require later spatial/locality checks.
    result['building_match_key'] = result['building_match_key'] if result['city'] and not flags else ''
    result['unit_match_key'] = result['unit_match_key'] if result['city'] and not flags else ''
    if kind != 'street_address' or flags:
        result['normalized_full_address'] = text
        result['normalized_delivery_address'] = text
    result['cad_normalization_version'] = VERSION
    return result
