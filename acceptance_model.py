"""Small PDF-derived diagnostic, not an independent state-accuracy evaluation."""
import json, hashlib
from unittest.mock import patch
import engine

m=engine.memories(next(x for x in engine.DATA if x['sample_id']=='conv-26'))
turns={'D2:8','D13:1','D19:1'}
fixture=[x for x in m if x['source']['turn'] in turns]
assert len(fixture)==3
with patch.object(engine,'vector',return_value=fixture):
    result=engine.answer('conv-26','What is Caroline’s latest progress with adoption agencies?','dynamic',3)
state={x['id'].split('_')[-1]:x['state'] for x in result['memories']}
relation_keys={(x['from_id'].split('_')[-1],x['to_id'].split('_')[-1],x['type']) for x in result['relations']}
expected_updates={('D2:8','D13:1','UPDATE'),('D13:1','D19:1','UPDATE')}
output={'fixture_source':'PDF page 12 example, not independent labels','retrieval':'forced to 3 PDF turns; not a retrieval test','model':engine.MODEL,'engine_sha256':hashlib.sha256((engine.ROOT/'engine.py').read_bytes()).hexdigest(),'expected_latest_turn':'D19:1','latest_marked_active':state.get('D19:1')=='ACTIVE','expected_updates_present':expected_updates.issubset(relation_keys),'states':state,'relations':result['relations'],'answer':result['answer'],'evidence':[{x['source']['turn']:x['content']} for x in fixture]}
(engine.ROOT/'adoption-diagnostic.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(output,ensure_ascii=False))
