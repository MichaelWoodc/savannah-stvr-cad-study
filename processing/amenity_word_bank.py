"""Rebuild a source-audited lexical census of matched listings, including zero-call parcels."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from collections import Counter, defaultdict
import hashlib, json, re
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
STOP=set('a an the and or to of in on for with is are be this that it you your our we as at by from have has all can will not no into its also each these there their they but if so than then was were up out just only very more most some any'.split())

def run():
    out=ROOT/'amenity_word_bank';out.mkdir(exist_ok=True)
    cache=out/'source_cache';cache.mkdir(exist_ok=True)
    data=json.loads((ROOT/'amenity_votes/data.js').read_text(encoding='utf-8').split('=',1)[1].strip().rstrip(';'))
    audit=pd.read_csv(ROOT/'processed_data/listing_matches/verified_listing_matches.csv',dtype=str).fillna('')
    def read(row):
        target=cache/(row.listing_id+'.txt')
        raw=target.read_bytes() if target.exists() else Path(row.source_path).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==row.details_sha256, row.listing_id
        if not target.exists():target.write_bytes(raw)
        return row.listing_id,raw.decode('utf-8-sig'),row.details_sha256
    sources=dict((key,(body,sha)) for key,body,sha in ThreadPoolExecutor(max_workers=10).map(read,audit.itertuples()))
    evidence=[];listing_terms={};vocab=Counter();census=[]
    for listing_id,(body,sha) in sources.items():
        section='';terms=defaultdict(set);counts=Counter()
        for line_number,line in enumerate(body.splitlines(),1):
            if line.startswith('==='):
                section=line.strip('= ').upper();continue
            if section not in ('FULL DESCRIPTION','AMENITIES') or not line.strip():continue
            low=line.lower()
            context='restriction' if re.search(r'\b(no|not|prohibited|forbidden|unavailable|not allowed|not included)\b',low) else 'nearby' if re.search(r'\b(nearby|walking distance|walk to|minutes? away|blocks? away|short drive)\b',low) else 'amenities' if section=='AMENITIES' else 'description'
            words=re.findall(r"[a-z]+(?:'[a-z]+)?",low)
            found=set()
            for n in (1,2,3):
                for i in range(len(words)-n+1):
                    chunk=words[i:i+n]
                    if any(w in STOP or len(w)<3 for w in chunk):continue
                    term=' '.join(chunk);found.add(term);counts[term]+=1
            terms[context].update(found)
            if found:evidence.append(dict(listing_id=listing_id,section=section,context=context,line=line_number,text=line,sha256=sha,terms='|'.join(sorted(found))))
        listing_terms[listing_id]={k:sorted(v) for k,v in terms.items()}
        vocab.update(set().union(*terms.values()) if terms else set())
        census.extend(dict(listing_id=listing_id,term=t,occurrences=c) for t,c in counts.items())
    properties=[];memberships=[]
    for p in data['properties']:
        p={**p,'word_bank':{}}
        for context in ['description','amenities','restriction','nearby']:
            p['word_bank'][context]=sorted({t for l in p['listings'] for t in listing_terms[l['listing_id']].get(context,[])})
            memberships.extend(dict(pin=p['pin'],address=p['address'],context=context,term=t) for t in p['word_bank'][context])
        properties.append(p)
    stats=[]
    for context in ['positive','amenities','restriction','nearby']:
        groups=defaultdict(list)
        for p in properties:
            terms=set(p['word_bank']['description']+p['word_bank']['amenities']) if context=='positive' else p['word_bank'][context]
            for t in terms:groups[t].append(p)
        for term,ps in groups.items():
            row=dict(term=term,context=context,properties=len(ps))
            for scope in ['direct','combined']:
                years=data['years']['Noise-party-disturbance']
                exposure=sum((.59 if scope=='direct' else .59+p['neighbor_count'])*years for p in ps)
                calls=sum(p['counts'][scope]['Noise-party-disturbance'] for p in ps)
                row.update({scope+'_calls':calls,scope+'_annual_rate':calls/exposure,scope+'_expected':exposure*data['baselines']['Noise-party-disturbance'],scope+'_excess':calls-exposure*data['baselines']['Noise-party-disturbance']})
            stats.append(row)
    pd.DataFrame(evidence).to_csv(out/'source_line_evidence.csv',index=False)
    pd.DataFrame(census).to_csv(out/'listing_word_occurrences.csv',index=False)
    pd.DataFrame(memberships).to_csv(out/'property_word_bank.csv',index=False)
    pd.DataFrame(stats).sort_values('direct_excess',ascending=False).to_csv(out/'word_associations.csv',index=False)
    baselines=[dict(outcome=k,residential_properties=data['summary']['residential_baseline_properties'],years=data['years'][k],annual_calls_per_property=v) for k,v in data['baselines'].items()]
    pd.DataFrame(baselines).to_csv(out/'residential_references.csv',index=False)
    payload=dict(properties=properties,baselines=data['baselines'],years=data['years'],summary=data['summary'],listing_terms=listing_terms,terms=sorted(vocab),source_hashes={k:v[1] for k,v in sources.items()})
    (out/'data.js').write_text('window.WORD_BANK='+json.dumps(payload,ensure_ascii=True,separators=(',',':'))+';',encoding='utf-8')
    summary=dict(listings=len(sources),properties=len(properties),unique_terms=len(vocab),source_lines=len(evidence),property_context_terms=len(memberships))
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    (out/'README.md').write_text('''# Matched listing word bank

Rebuild: `python -m processing.amenity_word_bank`. Open index.html for live ranking and property/call inspection.

Every audited matched listing is included, including zero-call properties. Sources are hash-checked against the match audit and cached locally. Only FULL DESCRIPTION and AMENITIES sections are read; duplicated page text, reviews, host metadata and coordinates are excluded. All alphabetic content words and adjacent two/three-word phrases are counted after a fixed grammatical stopword filter. Every retained term is exported, with exact source lines and SHA256. Counts are descriptive word occurrences, not verified amenity counts.

Restriction/unavailable and nearby-attraction lines are separate heuristic contexts. Negation detection is conservative and sentence/line based, not a semantic guarantee. Review evidence before treating a phrase as on-site. A parcel contributes once per term regardless of repeated words or multiple listings. Multiple terms can receive the same call. Shared neighbors create overlapping memberships. Rankings are exploratory, unadjusted associations, not evidence that a word or amenity causes calls. Capacity, location and other confounding remain. Searching thousands of words creates chance extremes; minimum support does not establish significance.

The live page defaults to an explicit party/social/leisure relevance vocabulary independent of call counts; disable the relevance checkbox to inspect every raw term. Optional signed votes give each above-reference advertiser +1 and each below-reference advertiser -1, including zero-call properties. Optional with/without contrast requires minimum support on both sides and overrides these scores. Raw CSV exports retain the full vocabulary. Contextual model analysis runs separately at ../party_sentiment/index.html.

Residential references include all 4,806 eligible parcels, including zeros, in the fixed study footprint, not the whole city. Same-category reference is the comparable default; all-citizen reference is contextual when the selected outcome is narrower. The reference never changes with word filters. Calendar exposure uses observed coverage, not a full year for partial years. Parking has shorter coverage. Booking adjustment affects rental exposure only, not neighbors. Counts include citizen-initiated calls with patrol/proactive exclusions only.
''',encoding='utf-8')
    print(json.dumps(summary),flush=True)

if __name__=='__main__':run()
