import argparse, collections, datetime, hashlib, json, os, re, statistics, string
import engine

def normalize(s):
    s=str(s).lower(); s=''.join(c for c in s if c not in string.punctuation); return re.sub(r'\b(a|an|the)\b',' ',s).split()
def f1(a,b):
    a,b=normalize(a),normalize(b); overlap=sum((collections.Counter(a)&collections.Counter(b)).values())
    if not a or not b: return float(a==b)
    if not overlap: return 0.0
    p=overlap/len(a); r=overlap/len(b); return 2*p*r/(p+r)
def select(qa, limit):
    # Category 5 is unanswerable and has no gold answer; exclude from QA F1.
    eligible=[(i,q) for i,q in enumerate(qa) if q.get('category')!=5 and q.get('answer') is not None]
    if not limit: return eligible
    groups={c:[(i,q) for i,q in eligible if q.get('category')==c] for c in (1,2,3,4)}
    selected=[]
    while len(selected)<limit and any(groups.values()):
        for c in groups:
            if groups[c] and len(selected)<limit: selected.append(groups[c].pop(0))
    return selected

def aggregate(rows):
    out={}
    for method in sorted({r['method'] for r in rows}):
        subset=[r for r in rows if r['method']==method]; good=[r for r in subset if 'error' not in r]
        recalls=[r['evidence_recall'] for r in good if r['evidence_recall'] is not None]
        out[method]={'attempted':len(subset),'scored':len(good),'errors':len(subset)-len(good),'mean_answer_f1_success_only':statistics.mean(r['answer_f1'] for r in good) if good else None,'mean_answer_f1_errors_as_zero':sum(r['answer_f1'] for r in good)/len(subset) if subset else None,'mean_evidence_recall':statistics.mean(recalls) if recalls else None,'evidence_recall_denominator':len(recalls)}
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--split',choices=['development','test'],default='test');p.add_argument('--limit',type=int,default=4,help='stratified questions per conversation; 0 for all answerable');p.add_argument('--methods',nargs='+',choices=['dynamic','vector','hybrid','full'],default=['dynamic','vector','hybrid','full']);p.add_argument('--output',default='evaluation.json');p.add_argument('--k',type=int,default=15);args=p.parse_args()
    if args.limit<0 or args.k<1: p.error('limit must be nonnegative; k must be positive')
    rows=[]; started=datetime.datetime.now().isoformat(timespec='seconds'); engine_hash=hashlib.sha256((engine.ROOT/'engine.py').read_bytes()).hexdigest(); data_hash=hashlib.sha256((engine.ROOT/'locomo10.json').read_bytes()).hexdigest(); expected=sum(len(select(s['qa'],args.limit)) for s in engine.DATA if s['sample_id'] in engine.SPLIT[args.split])*len(args.methods)
    def save():
        output={'started_local':started,'split':args.split,'sample_ids':engine.SPLIT[args.split], 'selection':'First answerable question in each category 1–4 in source order, cycling until limit; category 5 excluded because it has no gold answer. limit=0 uses all answerable questions.', 'limit_per_conversation':args.limit,'k':args.k,'engine_sha256':engine_hash,'data_sha256':data_hash,'expected_rows':expected,'completed':len(rows)==expected, 'answer_model':engine.MODEL,'embedding_model':os.getenv('EMBED_MODEL','bge-m3'),'full_evidence_note':'Full-text evidence recall is not scored: context truncation cannot be excluded.', 'dynamic_state_accuracy':None,'dynamic_state_accuracy_reason':'No instructor-provided or independently annotated relation labels','summary':aggregate(rows),'rows':rows}
        path=engine.ROOT.joinpath(args.output);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf8');tmp.replace(path)
    for sample in engine.DATA:
        if sample['sample_id'] not in engine.SPLIT[args.split]: continue
        for idx,qa in select(sample['qa'],args.limit):
            for method in args.methods:
                row={'sample':sample['sample_id'],'qa_index':idx,'category':qa.get('category'),'method':method,'question':qa['question'],'gold_answer':qa['answer'],'gold_evidence':qa.get('evidence',[])}
                try:
                    result=engine.answer(sample['sample_id'],qa['question'],method,args.k)
                    ev=set(qa.get('evidence',[]));got={x['source']['turn'] for x in result['retrieved']};pred=result['answer']
                    row.update(prediction=pred,answer_f1=f1(pred,qa['answer']),evidence_recall=(len(ev&got)/len(ev) if ev and method!='full' else None),retrieved_turns=sorted(got),states=result.get('memories',[]),relations=result.get('relations',[]))
                except Exception as e: row['error']=str(e)
                rows.append(row);save(); print(json.dumps({k:v for k,v in row.items() if k!='retrieved_turns'},ensure_ascii=False),flush=True)
    save()
if __name__=='__main__':main()
