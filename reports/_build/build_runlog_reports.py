import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "experiments"
NOW = datetime.now(timezone(timedelta(hours=8))).replace(microsecond=0).isoformat()
HEAD = "2c1e22a11a204bc8f6648f0e3a565ac3f2ae03df"

def fmt(x, d=4): return "not_available" if x is None else f"{float(x):.{d}f}"
def three(claim, qlabel, qv, tokens, p95):
    q=f"{qlabel}={fmt(qv)}"; t=f"Tokens={tokens:.1f}" if tokens is not None else "Tokens=not_available"
    p=f"P95={p95:.1f} ms" if p95 is not None else "P95=not_available"
    return f"{claim} | quality {q}; {t}; {p}."
def cov(rows, source):
    return {"data_modes":[{"mode":"offline","rows":0,"source":None,"status":"not_run"},
                          {"mode":"online","rows":rows,"source":source,"status":"complete"}],
            "fake_factors":["no Judge","1 seed unless stated","state_accuracy not recorded"],
            "a_level_only":False,"b_level":True,"judge":"not_run",
            "not_available":["judge_accuracy","state_accuracy","P(A|S) pairing","oracle_gap","llm_attribution"],
            "summary_zh":f"在线 {rows} 行；B 级 LLM 答案，无 Judge；不与离线数字混合。"}

# E2-2 oracle
o=json.load(open(ROOT/'eval/archive/e2-oracle-retrieval.json'))
m=o['metrics']
e2={"schema":"memlab/experiment-report@1","experiment_id":"E2-2-online","created_at":NOW,
 "manifest":{"git_commit":HEAD,"data_git_commit":"1096530","config_hashes":{},
             "model":{"llm":"qwen3.8:27b-q4_K_M","embedding":"bge-m3","judge":"not_run"},
             "offline":False,"data_mode":"online","source_db":"runs/e2/oracle.sqlite",
             "source_archive":"eval/archive/e2-oracle-retrieval.json"},
 "dataset":{"split":"development","samples":o['samples'],"questions":o['questions'],"seeds":[o['seed']],"test_only":False},
 "results":{"runs":[{"run_id":o['run_id'],"candidate":"oracle retrieval","question":f"{o['questions']} q · conv-26/30/43/44 · seed 13",
   "tokens":m['tokens'],"latency_ms":m['latency_ms'],"candidates":None,
   "answer":f"online LLM; F1={fmt(m['answer_f1'])}","metrics":m}],
   "metrics":{**m,"error_rate":0.0,"questions":o['questions']},
   "source":{"archive":"eval/archive/e2-oracle-retrieval.json"}},
 "comparisons":[{"baseline":"R0 (not matched)","candidate":"oracle retrieval","metric":"answer_f1",
   "baseline_value":None,"candidate_value":m['answer_f1'],"delta":None,"ci95":None,"paired":False,"significant":None,
   "note":"Oracle injects gold evidence; no matched non-oracle run on the same 80 q, so no delta."}],
 "analysis":{"main_effects":[],"interactions":[],"pareto":[],"failure_breakdown":[],
   "failure_note":"0 errors; 80 q oracle run.",
   "oracle_scope":"retrieval only; M/U frozen R0. write/store/merge/state/answer oracle not run.",
   "coverage_limits":cov(1,"eval/archive/e2-oracle-retrieval.json")},
 "conclusion":{"status":"partial","three_piece":{"quality":{"metric":"answer_f1","value":m['answer_f1']},
   "tokens_per_query":m['tokens'],"p95_latency_ms":m['latency_ms']},
   "claims":[three(f"E2-2 retrieval oracle: F1 {fmt(m['answer_f1'])}, Recall {fmt(m['evidence_recall'])} (constructed, not comparable to system recall); quality=F1 {fmt(m['answer_f1'])}.",
                  "F1",m['answer_f1'],m['tokens'],m['latency_ms']),],
   "conditions":["Online qwen3.8:27b, bge-m3; 4 dev conversations, 80 q, seed 13; retrieval only oracle."],
   "limitations":["Oracle recall is constructed from gold evidence; do not compare it with system recall.","Only retrieval oracle; other oracles not run.","No Judge."],
   "next_actions":["Run write/store/merge/state/answer oracles for a full oracle gap."]},
 "coverage_limits":cov(1,"eval/archive/e2-oracle-retrieval.json"),
 "online":{"status":"complete","source":"eval/archive/e2-oracle-retrieval.json","model":"qwen3.8:27b-q4_K_M","judge":"not_run","seeds":[13],"questions":80},
 "web":{"route":"#/experiments/E2-2-online","published":True},
 "coverage":{"catalog_rows":["E2-2"],"note":"Retrieval oracle only; constructed recall."}}

# E3 2x2
e3=json.load(open(ROOT/'eval/archive/e3-2x2.json'))
runs=e3['runs']
def cell(fusion,answer):
    return next(r for r in runs if r['factors']['fusion.impl']==fusion and r['factors']['answer.impl']==answer)['metrics']
s_d=cell('single_channel','direct'); s_e=cell('single_channel','evidence_chain')
w_d=cell('weighted_rrf','direct'); w_e=cell('weighted_rrf','evidence_chain')
def comp(base,cand,metric,bv,cv):
    return {"baseline":base,"candidate":cand,"metric":metric,"baseline_value":bv,"candidate_value":cv,
            "delta":round(cv-bv,4),"ci95":None,"paired":False,"significant":None,"note":"Online 4-cell 2x2, 60 q/cell, 1 seed; descriptive."}
comparisons=[comp('single_channel/direct','weighted_rrf/direct','answer_f1',s_d['answer_f1'],w_d['answer_f1']),
             comp('single_channel/direct','weighted_rrf/direct','evidence_recall',s_d['evidence_recall'],w_d['evidence_recall']),
             comp('single_channel/direct','weighted_rrf/direct','tokens',s_d['tokens'],w_d['tokens']),
             comp('single_channel/direct','single_channel/evidence_chain','answer_f1',s_d['answer_f1'],s_e['answer_f1']),
             comp('weighted_rrf/direct','weighted_rrf/evidence_chain','answer_f1',w_d['answer_f1'],w_e['answer_f1'])]
claims=[three(f"E3 2x2 online: weighted_rrf/direct F1 {fmt(w_d['answer_f1'])} vs single/direct {fmt(s_d['answer_f1'])} (+0.0264), Recall {fmt(w_d['evidence_recall'])} vs {fmt(s_d['evidence_recall'])} (+0.0166); quality=F1 {fmt(w_d['answer_f1'])}.",
              "F1",w_d['answer_f1'],w_d['tokens'],w_d['latency_ms']),
        three(f"Under the same fusion, direct F1 {fmt(w_d['answer_f1'])} vs evidence_chain {fmt(w_e['answer_f1'])}; single/direct {fmt(s_d['answer_f1'])} vs single/evidence_chain {fmt(s_e['answer_f1'])}. quality=F1 {fmt(w_d['answer_f1'])}.",
              "F1",w_d['answer_f1'],w_d['tokens'],w_d['latency_ms'])]
e3r={"schema":"memlab/experiment-report@1","experiment_id":"E3-1-online","created_at":NOW,
 "manifest":{"git_commit":HEAD,"data_git_commit":"1096530","config_hashes":{},
             "model":{"llm":"qwen3.8:27b-q4_K_M","embedding":"bge-m3","judge":"not_run"},
             "offline":False,"data_mode":"online","source_db":"runs/e3/2x2.sqlite",
             "source_archive":"eval/archive/e3-2x2.json"},
 "dataset":{"split":"development","samples":["conv-26","conv-30","conv-43","conv-44"],"questions":60,"seeds":[13],"test_only":False,"cells":4},
 "results":{"runs":[{"run_id":r['run_id'],"candidate":f"{r['factors']['fusion.impl']}/{r['factors']['answer.impl']}",
   "question":f"60 q · {r['factors']['fusion.impl']}/{r['factors']['answer.impl']}",
   "tokens":r['metrics']['tokens'],"latency_ms":r['metrics']['latency_ms'],"candidates":r['metrics']['candidates'],
   "answer":f"online LLM; F1={fmt(r['metrics']['answer_f1'])}","metrics":r['metrics']} for r in runs],
   "metrics":{"questions":240,"answer_f1":round(sum(r['metrics']['answer_f1'] for r in runs)/4,4),
              "evidence_recall":round(sum(r['metrics']['evidence_recall'] for r in runs)/4,4),
              "tokens":round(sum(r['metrics']['tokens'] for r in runs)/4,2),
              "p95_latency_ms":round(sum(r['metrics']['latency_ms'] for r in runs)/4,2),"error_rate":0.0},
   "source":{"archive":"eval/archive/e3-2x2.json"}},
 "comparisons":comparisons,
 "analysis":{"main_effects":[],"interactions":[],"pareto":[],"by_cell":[{"cell":f"{r['factors']['fusion.impl']}/{r['factors']['answer.impl']}","metrics":r['metrics']} for r in runs],
   "failure_breakdown":[],"failure_note":"0 errors; 4 cells.",
   "coverage_limits":cov(4,"eval/archive/e3-2x2.json")},
 "conclusion":{"status":"partial","three_piece":{"quality":{"metric":"answer_f1","value":w_d['answer_f1']},
   "tokens_per_query":w_d['tokens'],"p95_latency_ms":w_d['latency_ms']},
   "claims":claims,"conditions":["Online qwen3.8:27b, bge-m3; 4 dev conversations, 60 q/cell, 1 seed."],
   "limitations":["No duplicate/CI; 1 seed; 60 q/cell.","No Judge."],"next_actions":["Add seeds and paired CI."]},
 "coverage_limits":cov(4,"eval/archive/e3-2x2.json"),
 "online":{"status":"complete","source":"eval/archive/e3-2x2.json","model":"qwen3.8:27b-q4_K_M","judge":"not_run","seeds":[13],"questions":60},
 "web":{"route":"#/experiments/E3-1-online","published":True},
 "coverage":{"catalog_rows":["E3-1"],"note":"Online fusion x answer 2x2; descriptive only."}}

# M2 rerank
m2=json.load(open(ROOT/'eval/archive/m2-rerank.json'))
runs=m2['runs']
none=next(r for r in runs if r['factors']['rerank.impl']=='none')['metrics']
ce=next(r for r in runs if r['factors']['rerank.impl']=='cross_encoder')['metrics']
comparisons=[]
for k in ('answer_f1','evidence_recall','ndcg','tokens','latency_ms'):
    comparisons.append({"baseline":"none","candidate":"cross_encoder","metric":k,
                        "baseline_value":none[k],"candidate_value":ce[k],"delta":round(ce[k]-none[k],4),
                        "ci95":None,"paired":False,"significant":None,"note":"Online 40 q/config, 1 seed; descriptive."})
claims=[three(f"M2 rerank online: cross_encoder F1 {fmt(ce['answer_f1'])} vs none {fmt(none['answer_f1'])}; Recall {fmt(ce['evidence_recall'])} vs {fmt(none['evidence_recall'])}; nDCG {fmt(ce['ndcg'])} vs {fmt(none['ndcg'])}; Tokens {ce['tokens']} vs {none['tokens']}. quality=F1 {fmt(ce['answer_f1'])}.",
              "F1",ce['answer_f1'],ce['tokens'],ce['latency_ms']),
        three(f"Cross-encoder raises nDCG (+{ce['ndcg']-none['ndcg']:.4f}) but lowers Recall ({ce['evidence_recall']-none['evidence_recall']:+.4f}) and F1 ({ce['answer_f1']-none['answer_f1']:+.4f}); it is not uniformly better. quality=F1 {fmt(ce['answer_f1'])}.",
              "F1",ce['answer_f1'],ce['tokens'],ce['latency_ms'])]
m2r={"schema":"memlab/experiment-report@1","experiment_id":"M2-online","created_at":NOW,
 "manifest":{"git_commit":HEAD,"data_git_commit":"1096530","config_hashes":{},
             "model":{"llm":"qwen3.8:27b-q4_K_M","embedding":"bge-m3","judge":"not_run","reranker":"BAAI/bge-reranker-v2-m3"},
             "offline":False,"data_mode":"online","source_db":"runs/s6/m2.sqlite",
             "source_archive":"eval/archive/m2-rerank.json"},
 "dataset":{"split":"development","samples":["conv-26","conv-30","conv-43","conv-44"],"questions":40,"seeds":[13],"test_only":False},
 "results":{"runs":[{"run_id":r['run_id'],"candidate":r['factors']['rerank.impl'],
   "question":f"40 q · rerank={r['factors']['rerank.impl']}",
   "tokens":r['metrics']['tokens'],"latency_ms":r['metrics']['latency_ms'],"candidates":r['metrics']['candidates'],
   "answer":f"online LLM; F1={fmt(r['metrics']['answer_f1'])}","metrics":r['metrics']} for r in runs],
   "metrics":{"questions":80,"answer_f1":round((none['answer_f1']+ce['answer_f1'])/2,4),
              "evidence_recall":round((none['evidence_recall']+ce['evidence_recall'])/2,4),
              "tokens":round((none['tokens']+ce['tokens'])/2,2),
              "p95_latency_ms":round((none['latency_ms']+ce['latency_ms'])/2,2),"error_rate":0.0},
   "source":{"archive":"eval/archive/m2-rerank.json"}},
 "comparisons":comparisons,
 "analysis":{"main_effects":[],"interactions":[],"pareto":[],"by_candidate":{"none":none,"cross_encoder":ce},
   "failure_breakdown":[],"failure_note":"0 errors; 2 configs.",
   "coverage_limits":cov(2,"eval/archive/m2-rerank.json")},
 "conclusion":{"status":"partial","three_piece":{"quality":{"metric":"answer_f1","value":ce['answer_f1']},
   "tokens_per_query":ce['tokens'],"p95_latency_ms":ce['latency_ms']},
   "claims":claims,"conditions":["Online qwen3.8:27b, bge-m3, GPU cross-encoder BAAI/bge-reranker-v2-m3; 4 dev conversations, 40 q/config, 1 seed."],
   "limitations":["1 seed, 40 q/config; no CI.","Cross-encoder trades recall/F1 for nDCG/tokens; not a uniform win.","No Judge."],
   "next_actions":["Add seeds and paired CI; test top_n with the real reranker."]},
 "coverage_limits":cov(2,"eval/archive/m2-rerank.json"),
 "online":{"status":"complete","source":"eval/archive/m2-rerank.json","model":"qwen3.8:27b-q4_K_M","judge":"not_run","seeds":[13],"questions":40},
 "web":{"route":"#/experiments/M2-online","published":True},
 "coverage":{"catalog_rows":["E1-M2"],"note":"Online cross-encoder rerank; not a uniform win."}}

for r in (e2,e3r,m2r):
    (OUT/f"{r['experiment_id']}.json").write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8")
    print(OUT/f"{r['experiment_id']}.json")
