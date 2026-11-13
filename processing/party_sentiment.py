"""Local, resumable, call-blind contextual screening of every validated listing."""
from pathlib import Path
import argparse, csv, hashlib, io, json, os, re, sqlite3, tempfile, time, traceback
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'party_sentiment'
MODEL='MoritzLaurer/deberta-v3-base-zeroshot-v1.1-all-33'
HYPOTHESES={
    'party_welcome':'The host explicitly welcomes parties, celebrations or events at this rental property.',
    'social_amenities':'The rental itself offers leisure or entertainment amenities for socializing, such as a hot tub, pool, games, bar, barbecue or outdoor gathering space.',
    'party_restriction':'The host prohibits parties, events, loud noise or disruptive gatherings at this property.',
    'nearby_nightlife':'The text describes bars, nightlife, entertainment venues or party activities nearby rather than at the rental itself.'
}

def invitation_evidence(text):
    """Conservative, auditable gate: an event and affirmative marketing in one sentence."""
    for sentence in re.split(r'(?<=[.!?])\s+',text):
        low=sentence.lower()
        # Travel-group homonyms must not establish an event claim.
        event_text=re.sub(r'\b(?:your|our|their|the|travel|traveling|travelling) party\b|\bparty of\b','travel group',low)
        event=bool(re.search(r'\b(parties|party|celebrations?|events?|gatherings?|reunions?|weddings?|birthdays?|bachelorette|bachelor)\b',event_text))
        action=bool(re.search(r'\b(welcome|welcomes|allowed|permitted|hosting|host|celebrate|celebrating|venue)\b|\b(?:perfect|ideal|great|suited|suitable)\b.{0,55}\bfor\b',low))
        negative=bool(re.search(r'\b(no|not|prohibited|forbidden|banned|disallowed)\b',low))
        if event and action and not negative:return sentence
    return None

def atomic(path,text):
    # Preview/file watchers can briefly hold Windows files without delete sharing.
    # Keep the previous complete file visible while retrying the atomic replace.
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
            prefix=path.name+'.',suffix='.tmp',delete=False) as stream:
        temp=Path(stream.name);stream.write(text)
    try:
        for attempt in range(60):
            try:
                os.replace(temp,path)
                return
            except OSError as error:
                if getattr(error,'winerror',None) not in (5,32,33) or attempt==59:
                    raise
                time.sleep(min(.05*2**min(attempt,5),1))
    finally:
        temp.unlink(missing_ok=True)

def status(**kwargs):
    obj=dict(updated_utc=datetime.now(timezone.utc).isoformat(),pid=os.getpid(),**kwargs)
    atomic(OUT/'status.json',json.dumps(obj,indent=2));atomic(OUT/'status.js','window.PARTY_STATUS='+json.dumps(obj)+';')

def chunks(body):
    """All description/amenity text, no reviews/duplicate page/metadata, <=110 words."""
    section='';block=[];start=0
    for number,line in enumerate(body.splitlines(),1):
        if line.startswith('==='):
            if block:yield dict(text=' '.join(block),section=section,line=start);block=[]
            section=line.strip('= ').upper();continue
        if section not in ('FULL DESCRIPTION','AMENITIES') or not line.strip():continue
        # Keep sentence boundaries when possible; split oversized sentences rather than drop tails.
        for sentence in re.split(r'(?<=[.!?])\s+',line.strip()):
            words=sentence.split()
            for pos in range(0,len(words),100):
                part=' '.join(words[pos:pos+100])
                if block and len((' '.join(block)+' '+part).split())>110:
                    yield dict(text=' '.join(block),section=section,line=start);block=[]
                if not block:start=number
                block.append(part)
    if block:yield dict(text=' '.join(block),section=section,line=start)

def publish(results,bank,meta):
    listing_map={r['listing_id']:r for r in results}
    properties=[]
    for p in bank['properties']:
        # Keep unprocessed and zero-call properties, and report coverage explicitly.
        listings=[dict(listing_id=l['listing_id'],title=l['title'],url=l['url'],guests=l['guests'],permits=l['permits'],analysis=listing_map.get(l['listing_id'])) for l in p['listings']]
        properties.append({k:p[k] for k in ['pin','address','permit_type','approved_guests','advertised_guests','neighbor_count','counts','calls']}|dict(listings=listings,complete=all(l['analysis'] for l in listings)))
    payload=dict(properties=properties,baselines=bank['baselines'],years=bank['years'],summary=bank['summary'],meta=meta)
    atomic(OUT/'data.js','window.PARTY_SENTIMENT='+json.dumps(payload,ensure_ascii=True,separators=(',',':'))+';')
    if results:
        fields=['listing_id','source_sha256','chunks','words','party_signal','social_signal',*HYPOTHESES]
        stream=io.StringIO(newline='')
        w=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(results)
        atomic(OUT/'listing_scores.csv',stream.getvalue())

def run(limit=None):
    OUT.mkdir(exist_ok=True);start=time.time();total=0;results=[]
    status(state='loading',completed=0,model=MODEL)
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        assert torch.cuda.is_available(), 'CUDA unavailable; refusing silent CPU fallback.'
        torch.set_num_threads(4)
        bank=json.loads((ROOT/'amenity_word_bank/data.js').read_text(encoding='utf-8').split('=',1)[1].rstrip(';'))
        audit=json.loads((ROOT/'listing_match_validation.js').read_text(encoding='utf-8').split('=',1)[1].strip().rstrip(';'))
        assert bank['summary']['source_hashes']['processed_data/listing_matches/source_match_audit.csv']==audit['audit_sha256']
        total=len(bank['source_hashes'])
        device=torch.cuda.get_device_name(0)
        tokenizer=AutoTokenizer.from_pretrained(MODEL,cache_dir=str(OUT/'model_cache'))
        model=AutoModelForSequenceClassification.from_pretrained(MODEL,cache_dir=str(OUT/'model_cache'),use_safetensors=True).to('cuda').eval()
        revision=model.config._commit_hash
        entail=[int(i) for i,label in model.config.id2label.items() if label.lower()=='entailment']
        assert len(entail)==1,model.config.id2label
        signature=hashlib.sha256(json.dumps([MODEL,revision,HYPOTHESES,'chunks110-invitation-gate-v2']).encode()).hexdigest()
        meta=dict(model=MODEL,revision=revision,signature=signature,hypotheses=HYPOTHESES,device=device,torch=torch.__version__,threshold=.8,notes='Call-blind zero-shot screening scores, not calibrated probabilities or confirmed behavior. Party signal additionally requires affirmative event-marketing language in one sentence; travel-group homonyms cannot supply the event. Review source excerpts.')
        atomic(OUT/'run_config.json',json.dumps(meta,indent=2))
        db=sqlite3.connect(OUT/'chunk_scores.sqlite');db.execute('CREATE TABLE IF NOT EXISTS scores (key TEXT PRIMARY KEY, value TEXT)')
        def score_texts(texts):
            pairs=[(t,h) for t in texts for h in HYPOTHESES.values()];values=[]
            for offset in range(0,len(pairs),8):
                batch=pairs[offset:offset+8]
                tokens=tokenizer([p[0] for p in batch],[p[1] for p in batch],padding=True,truncation='only_first',max_length=384,return_tensors='pt').to('cuda')
                with torch.inference_mode():probs=model(**tokens).logits.softmax(-1)[:,entail[0]].cpu().tolist()
                values.extend(probs)
            return [dict(zip(HYPOTHESES,values[i:i+len(HYPOTHESES)])) for i in range(0,len(values),len(HYPOTHESES))]
        probes=[('generic','Please message the host. Be aware of the smart locks.'),('prohibition','No parties or events are allowed. Keep noise down.'),('invitation','Host your birthday party here! Parties and celebrations are welcome at this house.'),('nearby','The home is a short walk from downtown bars and nightlife.'),('amenity','Enjoy our private hot tub, pool table, outdoor bar and barbecue patio.'),('travel_group','With a deadbolt on the apartment door, your party is always safe at our vacation rentals. Artwork welcomes your party.'),('catering_example','Our baker specializes in cakes. I frequently send her a photo of something I would like for a party or small gathering and she can make it!')]
        probe_results=[dict(case=key,text=text,scores=scores,affirmative_event_evidence=invitation_evidence(text)) for (key,text),scores in zip(probes,score_texts([p[1] for p in probes]))]
        atomic(OUT/'sanity_checks.json',json.dumps(probe_results,indent=2))
        # Save actual outputs even on a failed probe, but do not run a known-bad classifier overnight.
        assert probe_results[0]['scores']['party_welcome']<.5, 'Generic-language party probe failed.'
        assert probe_results[1]['scores']['party_welcome']<.5, 'No-parties party probe failed.'
        assert probe_results[2]['scores']['party_welcome']>.5, 'Explicit-party invitation probe failed.'
        assert not probe_results[5]['affirmative_event_evidence'], 'Travel-group homonym gate failed.'
        assert not probe_results[6]['affirmative_event_evidence'], 'Catering example gate failed.'
        assert probe_results[2]['affirmative_event_evidence'], 'Explicit invitation gate failed.'
        checkpoint=OUT/'listing_results.jsonl'
        if checkpoint.exists():
            for line in checkpoint.read_text(encoding='utf-8').splitlines():
                try:r=json.loads(line)
                except json.JSONDecodeError:continue
                if r.get('signature')==signature and bank['source_hashes'].get(r['listing_id'])==r['source_sha256']:results.append(r)
        completed={r['listing_id'] for r in results};publish(results,bank,meta)
        status(state='running',completed=len(results),total=total,device=device,model=MODEL)
        for listing_id,source_sha in sorted(bank['source_hashes'].items()):
            if listing_id in completed:continue
            raw=(ROOT/'amenity_word_bank/source_cache'/(listing_id+'.txt')).read_bytes()
            assert hashlib.sha256(raw).hexdigest()==source_sha
            parts=list(chunks(raw.decode('utf-8-sig')))
            scored=[]
            for i in range(0,len(parts),8):
                group=parts[i:i+8];keys=[hashlib.sha256((signature+p['text']).encode()).hexdigest() for p in group]
                cached=[db.execute('SELECT value FROM scores WHERE key=?',(key,)).fetchone() for key in keys]
                missing=[j for j,v in enumerate(cached) if v is None]
                fresh=score_texts([group[j]['text'] for j in missing]) if missing else []
                for j,value in zip(missing,fresh):
                    db.execute('INSERT OR REPLACE INTO scores VALUES (?,?)',(keys[j],json.dumps(value)));cached[j]=(json.dumps(value),)
                db.commit()
                scored.extend(dict(**p,scores=json.loads(v[0])) for p,v in zip(group,cached))
            eligible=[p for p in scored if p['scores']['party_restriction']<.5 and p['scores']['nearby_nightlife']<.5]
            invitation=[dict(**p,affirmative_event_evidence=invitation_evidence(p['text'])) for p in eligible if invitation_evidence(p['text'])]
            record=dict(listing_id=listing_id,signature=signature,source_sha256=source_sha,chunks=len(scored),words=sum(len(p['text'].split()) for p in parts),
                party_signal=max((p['scores']['party_welcome'] for p in invitation),default=0),social_signal=max((p['scores']['social_amenities'] for p in eligible),default=0),
                **{k:max((p['scores'][k] for p in scored),default=0) for k in HYPOTHESES},
                signal_evidence=sorted(invitation,key=lambda p:p['scores']['party_welcome'],reverse=True)[:2],
                social_evidence=sorted(eligible,key=lambda p:p['scores']['social_amenities'],reverse=True)[:2],
                evidence={k:sorted(scored,key=lambda p:p['scores'][k],reverse=True)[:2] for k in HYPOTHESES})
            with checkpoint.open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=True)+'\n');f.flush()
            results.append(record);completed.add(listing_id)
            status(state='running',completed=len(results),total=total,device=device,model=MODEL,elapsed_seconds=round(time.time()-start),last_listing=listing_id)
            print(f'{len(results)}/{total} listing {listing_id}; party={record["party_signal"]:.3f}; social={record["social_signal"]:.3f}',flush=True)
            if len(results)%5==0:publish(results,bank,meta)
            if limit and len(results)>=limit:break
        publish(results,bank,meta)
        status(state='complete' if len(results)==total else 'sample_complete',completed=len(results),total=total,device=device,model=MODEL,elapsed_seconds=round(time.time()-start))
        db.close()
    except Exception as error:
        status(state='failed',completed=len(results),total=total,error=str(error),traceback=traceback.format_exc());raise

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int);args=parser.parse_args();run(args.limit)
