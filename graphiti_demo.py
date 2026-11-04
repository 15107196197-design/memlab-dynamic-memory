"""Read-only view of the existing Graphiti/Kuzu demonstration graph."""
import gzip, json, os, shutil, tempfile
from pathlib import Path
import kuzu
import engine

root=engine.ROOT
custom=os.getenv('GRAPHITI_DEMO_DB')
path=Path(custom) if custom else root/'cache'/'graphiti-demo.kuzu'
if not custom and not path.exists():
    source=root/'examples'/'graphiti-demo.kuzu.gz'
    if not source.is_file(): raise FileNotFoundError('Compressed Graphiti demonstration not found: '+str(source))
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.tmp', delete=False) as dst:
            tmp=Path(dst.name)
            with gzip.open(source,'rb') as src: shutil.copyfileobj(src,dst)
        tmp.replace(path)
    finally:
        if tmp is not None: tmp.unlink(missing_ok=True)
if not path.is_file(): raise FileNotFoundError('Graphiti demo database not found: '+str(path))
db=kuzu.Database(str(path),read_only=True)
conn=kuzu.Connection(db)
def rows(query):
    r=conn.execute(query); result=[]
    while r.has_next(): result.append(r.get_next())
    return result
try:
    episodes=rows('MATCH (n:Episodic) RETURN n.uuid,n.name,n.source_description')
    edges=rows('MATCH (e:RelatesToNode_) RETURN e.fact,e.episodes,e.valid_at,e.invalid_at')
    original={x['source']['turn']:x for x in engine.memories(next(s for s in engine.DATA if s['sample_id']=='conv-26'))}
    source_map={uuid:{'turn':name,'description':description,'original':original.get(name)} for uuid,name,description in episodes}
    facts=[]
    for fact,uuids,valid,invalid in edges:
        facts.append({'fact':fact,'sources':[source_map[u] for u in uuids if u in source_map],'unmapped_episode_uuids':[u for u in uuids if u not in source_map],'valid_at':valid.isoformat() if valid else None,'invalid_at':invalid.isoformat() if invalid else None})
    print(json.dumps({'coverage':'conv-26 D2:8 / D13:1 / D19:1 only; not a complete conversation graph','engine':'Graphiti with deprecated Kuzu driver','time_note':'Original demo treated timezone-free local session times as UTC; do not interpret as verified UTC.','episodes':[v for v in source_map.values()],'facts':facts},ensure_ascii=True))
finally:
    conn.close();db.close()
