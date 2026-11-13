"""Conservative Publication 28 formatting for street addresses; no delivery validation."""
import re
import unicodedata

VERSION = '1.0.0'
DIRECTIONS = dict(zip('NORTH SOUTH EAST WEST NORTHEAST NORTHWEST SOUTHEAST SOUTHWEST'.split(),
                      'N S E W NE NW SE SW'.split()))
SUFFIXES = {}
for canonical, variants in {
    'ST': 'ST STREET STR', 'AVE': 'AVE AV AVENUE AVEN', 'LN': 'LN LANE',
    'RD': 'RD ROAD', 'DR': 'DR DRIVE', 'BLVD': 'BLVD BOULEVARD',
    'CT': 'CT COURT', 'CIR': 'CIR CIRCLE', 'PL': 'PL PLACE', 'TER': 'TER TERRACE',
    'WAY': 'WAY', 'WALK': 'WALK WK', 'HWY': 'HWY HIGHWAY', 'PKWY': 'PKWY PARKWAY',
    'ALY': 'ALY ALLEY', 'SQ': 'SQ SQUARE', 'TRL': 'TRL TRAIL', 'PT': 'PT POINT',
    'LOOP': 'LOOP', 'CV': 'CV COVE', 'PLZ': 'PLZ PLAZA', 'XING': 'XING CROSSING',
}.items():
    SUFFIXES.update({v: canonical for v in variants.split()})
UNITS = {'APARTMENT': 'APT', 'APT': 'APT', 'SUITE': 'STE', 'STE': 'STE',
         'UNIT': 'UNIT', 'BUILDING': 'BLDG', 'BLDG': 'BLDG', 'FLOOR': 'FL',
         'FL': 'FL', 'ROOM': 'RM', 'RM': 'RM', 'BASEMENT': 'BSMT',
         'LOWER': 'LOWR', 'UPPER': 'UPPR', 'REAR': 'REAR', 'FRONT': 'FRNT'}

def clean(value):
    if value is None or str(value).strip().lower() in ('', 'nan', '<na>', 'none'):
        return ''
    value = unicodedata.normalize('NFKC', str(value)).upper()
    value = value.replace('’', "'").replace("'", '').replace('.', '')
    return re.sub(r'\s+', ' ', value.replace(',', ' ')).strip()

def unit_part(value):
    text = clean(value)
    text = re.sub(r'^#\s*', '# ', text)
    if not text:
        return '', ''
    if re.fullmatch(r'[A-Z0-9]+(?:[-/][A-Z0-9]+)*', text) and text not in UNITS and text not in ('GARDEN', 'PARLOR', 'ADU', 'UPSTAIRS', 'DOWNSTAIRS'):
        return '#', text
    bits = text.split()
    if bits[0] == '#' and len(bits) == 2:
        return '#', bits[1]
    if bits[0] in UNITS and len(bits) <= 2:
        return UNITS[bits[0]], ' '.join(bits[1:])
    return '', ''

def normalize_address(address, unit=''):
    text = clean(address)
    flags = []
    city = state = zipcode = ''
    # Do not invent missing city/state/ZIP. This dataset supplies Savannah explicitly.
    last = re.search(r'\s+(SAVANNAH)\s+(GA|GEORGIA)\s+(\d{5}(?:-\d{4})?)$', text)
    if last:
        city, state, zipcode = last[1], 'GA', last[3]
        street = text[:last.start()]
    else:
        street = text
        flags.append('unparsed_or_missing_city_state_zip')
    number = pre = name = suffix = post = embedded = ''
    match = re.match(r'^(\d+[A-Z]?(?:-\d+[A-Z]?)?(?:\s+1/2)?)\s+(.+)$', street)
    if not match:
        flags.append('unparsed_street_address')
    else:
        number, rest = match.groups()
        words = rest.split()
        # Only directional positions are abbreviated, never tokens inside a street name.
        if words and words[0] in set(DIRECTIONS) | set(DIRECTIONS.values()):
            pre = DIRECTIONS.get(words.pop(0), rest.split()[0])
        candidates = [i for i, w in enumerate(words) if w in SUFFIXES and i > 0]
        if not candidates:
            name = ' '.join(words)
            flags.append('unrecognized_or_missing_street_suffix')
        else:
            i = candidates[-1]
            name, suffix = ' '.join(words[:i]), SUFFIXES[words[i]]
            tail = words[i+1:]
            if tail and tail[0] in set(DIRECTIONS) | set(DIRECTIONS.values()):
                post = DIRECTIONS.get(tail[0], tail[0])
                tail = tail[1:]
            embedded = ' '.join(tail)
    ed, ei = unit_part(embedded)
    sd, si = unit_part(unit)
    if embedded and not ed:
        flags.append('unparsed_embedded_unit')
    if clean(unit) and not sd:
        flags.append('unit_note_or_alternate_address_requires_review')
    if ed and sd and (ed, ei) != (sd, si):
        flags.append('conflicting_unit_fields')
    designator, identifier = (sd, si) if sd else (ed, ei)
    base = ' '.join(x for x in [number, pre, name, suffix, post] if x)
    delivery = ' '.join(x for x in [base, designator, identifier] if x)
    last_line = ' '.join(x for x in [city, state, zipcode] if x)
    return dict(address_original=address, unit_original=unit, house_number=number,
                predirectional=pre, street_name=name, street_suffix=suffix, postdirectional=post,
                embedded_unit_original=embedded, unit_designator=designator, unit_identifier=identifier,
                city=city, state=state, zip_code=zipcode, normalized_building_address=base,
                normalized_delivery_address=delivery, normalized_full_address=' '.join([delivery, last_line]).strip(),
                building_match_key='|'.join([base, city, state, zipcode]) if base and not any(f.startswith('unparsed_') or f.startswith('unrecognized_') for f in flags) else '',
                unit_match_key='|'.join([delivery, city, state, zipcode]) if not flags else '',
                review_required=bool(flags), review_reasons='; '.join(flags),
                normalization_version=VERSION, usps_delivery_validated=False)
