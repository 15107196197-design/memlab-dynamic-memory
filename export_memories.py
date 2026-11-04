import json
import engine
p=engine.ROOT/'exports';p.mkdir(exist_ok=True)
for x in engine.DATA:
    if x['sample_id'] in engine.SPLIT['development']+engine.SPLIT['test']:
        items=engine.memories(x);path=p/(x['sample_id']+'.json')
        path.write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf8')
        print(x['sample_id'],len(items),'processed',sum(m['fact_extraction']=='machine_unverified' for m in items))
