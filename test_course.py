import tempfile, json, unittest, threading, urllib.request, urllib.error
from pathlib import Path
from unittest.mock import patch
import app, engine, evaluate, extract

class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.sample=engine.DATA[0]; self.memories=engine.memories(self.sample)
    def test_lexical_retrieval_handles_inflection_and_question_words(self):
        top=engine.lexical('What did Caroline research?',self.memories,5)
        self.assertIn('D2:8',{x['source']['turn'] for x in top})
    def test_hybrid_recovers_development_evidence_missing_from_vector(self):
        m=self.memories; unrelated=[x for x in m if x['source']['turn']!='D2:8'][:15]
        def fake(prompt,json_mode): return {'answer':'unknown'}
        with patch.object(engine,'vector',return_value=unrelated), patch.object(engine,'generate',side_effect=fake):
            result=engine.answer('conv-26','What did Caroline research?','hybrid',15)
        self.assertIn('D2:8',{x['source']['turn'] for x in result['retrieved']})
    def test_import_is_persistent_and_rejects_duplicate_ids(self):
        sample={'sample_id':'custom-1','conversation':{'session_1_date_time':'1:00 pm on 1 May, 2023','session_1':[{'dia_id':'D1:1','speaker':'A','text':'hello'}]}}
        with tempfile.TemporaryDirectory() as directory, patch.object(engine,'IMPORT_DIR',Path(directory)),patch.object(engine,'DATA',[]):
            self.assertEqual(engine.import_samples(sample),['custom-1'])
            self.assertEqual(len(list(Path(directory).glob('*.json'))),1)
            with self.assertRaises(ValueError): engine.import_samples({**sample,'sample_id':'CUSTOM-1'})
            engine.DATA.clear(); engine.load_imported()
            self.assertEqual(engine.memories(engine.DATA[0])[0]['source']['turn'],'D1:1')
    def test_import_batch_rolls_back_if_second_commit_fails(self):
        sample={'sample_id':'a','conversation':{'session_1_date_time':'unknown','session_1':[{'dia_id':'D1:1','speaker':'A','text':'hi'}]}}
        original=Path.replace; calls=[]
        def flaky(path,target):
            calls.append(path)
            if len(calls)==2: raise OSError('disk error')
            return original(path,target)
        with tempfile.TemporaryDirectory() as directory, patch.object(engine,'IMPORT_DIR',Path(directory)),patch.object(engine,'DATA',[]),patch.object(Path,'replace',flaky):
            with self.assertRaises(OSError): engine.import_samples([sample,{**sample,'sample_id':'b'}])
            self.assertEqual(list(Path(directory).iterdir()),[]);self.assertEqual(engine.DATA,[])
    def test_invalid_import_batch_writes_nothing(self):
        valid={'sample_id':'safe','conversation':{'session_1_date_time':'unknown','session_1':[{'dia_id':'D1:1','speaker':'A','text':'hi'}]}}
        with tempfile.TemporaryDirectory() as directory, patch.object(engine,'IMPORT_DIR',Path(directory)),patch.object(engine,'DATA',[]):
            with self.assertRaises(ValueError): engine.import_samples([valid,{'sample_id':'../../bad','conversation':{}}])
            self.assertEqual(list(Path(directory).iterdir()),[])
    def test_development_and_test_splits_are_disjoint(self):
        dev=set(engine.SPLIT['development']); test=set(engine.SPLIT['test'])
        self.assertEqual(len(dev),4); self.assertEqual(len(test),2)
        self.assertTrue(dev.isdisjoint(test))
        self.assertEqual(test,{'conv-41','conv-42'})
    def test_dataset_observation_preserves_multiple_source_turns(self):
        sample={'observation':{'session_1_observation':{'Alex':[['Shared observation','D1:1, D1:2']]}}}
        mapped=engine.dataset_observations(sample)
        self.assertEqual(mapped['D1:1'][0]['source_turns'],['D1:1','D1:2'])
        self.assertEqual(mapped['D1:2'][0]['origin'],'dataset_annotation')
    def test_provenance_and_session_date(self):
        item=next(x for x in self.memories if x['source']['turn']=='D2:8')
        self.assertEqual(item['evidence']['dia_id'],'D2:8')
        self.assertEqual(engine.session_date(item['timestamp']).year,2023)
    def test_cutoff_excludes_future_recording_but_keeps_same_day(self):
        earlier=engine.apply_cutoff(self.memories,'2023-05-08')
        self.assertTrue(any(x['source']['turn']=='D1:3' for x in earlier))
        self.assertFalse(any(x['source']['turn']=='D2:8' for x in earlier))
        with self.assertRaises(ValueError): engine.apply_cutoff(self.memories,'May 2023')
    def test_baseline_and_dynamic_receive_same_candidates(self):
        retrieved=self.memories[:4]; captures=[]
        def fake(prompt,json_mode):
            captures.append(prompt)
            return {'answer':'test','memories':[{'id':retrieved[0]['memory_id'],'state':'HISTORICAL'},{'id':'invented','state':'ACTIVE'}], 'relations':[{'from_id':'invented','to_id':'invented','type':'UPDATE'}]}
        with patch.object(engine,'vector',return_value=retrieved),patch.object(engine,'lexical',return_value=[]),patch.object(engine,'generate',side_effect=fake):
            a=engine.answer('conv-26','question','dynamic',4);b=engine.answer('conv-26','question','hybrid',4)
        self.assertEqual({x['memory_id'] for x in a['retrieved']},{x['memory_id'] for x in b['retrieved']})
        self.assertEqual(a['relations'],[]);self.assertEqual(len(a['memories']),1);self.assertIn('Unknown',a['answer'])
    def test_generation_disables_truncation_and_shift(self):
        seen=[]
        def fake_post(path, body):
            seen.append(body)
            return {"response":'{"answer":"ok"}',"prompt_eval_count":3}
        with patch.object(engine,'post',side_effect=fake_post):
            self.assertEqual(engine.generate('query',True)['answer'],'ok')
        self.assertIs(seen[0]['truncate'],False)
        self.assertIs(seen[0]['shift'],False)
    def test_embedding_cache_is_valid_json_and_reused(self):
        def fake_post(path,body,**kwargs):
            inp=body['input'];return {'embeddings':[[1.0,0.0] for _ in (inp if isinstance(inp,list) else [inp])]}
        with tempfile.TemporaryDirectory() as directory,patch.object(engine,'ROOT',Path(directory)),patch.object(engine,'post',side_effect=fake_post) as post:
            first=engine.vector('test',self.memories[:2],2)
            self.assertEqual(post.call_count,2)
            engine.vector('test',self.memories[:2],2)
            self.assertEqual(post.call_count,3)
            cache=list((Path(directory)/'cache').iterdir());self.assertEqual(len(cache),1)
            self.assertEqual(len(json.loads(cache[0].read_text(encoding='utf8'))),2)
    def test_embedding_can_run_on_cpu_independently(self):
        with patch.dict('os.environ',{'EMBED_CPU_ONLY':'1','EMBED_THREADS':'2','MEMORY_GPU_LAYERS':'32'},clear=False):
            self.assertEqual(engine.embedding_options(),{'num_gpu':0,'num_thread':2})
            self.assertEqual(engine.model_options(),{'num_gpu':32})
    def test_cpu_only_options_apply_to_model_request(self):
        seen=[]
        def fake_post(path,body): seen.append(body); return {'response':'{"answer":"ok"}','prompt_eval_count':3}
        with patch.dict('os.environ',{'MEMORY_CPU_ONLY':'1','MEMORY_THREADS':'4'}), patch.object(engine,'post',side_effect=fake_post):
            engine.generate('query',True)
        self.assertEqual(seen[0]['options']['num_gpu'],0)
        self.assertEqual(seen[0]['options']['num_thread'],4)
    def test_generation_rejects_exhausted_context(self):
        with patch.object(engine,'post',return_value={"response":'{"answer":"ok"}',"prompt_eval_count":32767}):
            with self.assertRaises(ValueError): engine.generate('query',True)
    def test_self_relations_are_not_presented_as_memory_updates(self):
        m=self.memories[0]; mid=m['memory_id']
        result={'memories':[{'id':mid,'state':'HISTORICAL'}],'relations':[{'from_id':mid,'to_id':mid,'type':'RETAIN'}]}
        with patch.object(engine,'vector',return_value=[m]),patch.object(engine,'lexical',return_value=[]),patch.object(engine,'generate',return_value=result):
            out=engine.answer('conv-26','test','dynamic',1)
        self.assertEqual(out['relations'],[])
    def test_duplicate_conflicting_states_are_rejected(self):
        m=self.memories[0]
        result={'memories':[{'id':m['memory_id'],'state':'ACTIVE'},{'id':m['memory_id'],'state':'HISTORICAL'}],'relations':[]}
        with patch.object(engine,'vector',return_value=[m]),patch.object(engine,'lexical',return_value=[]),patch.object(engine,'generate',return_value=result):
            with self.assertRaises(ValueError): engine.answer('conv-26','test','dynamic',1)
    def test_generic_activity_overlap_is_flagged_but_specific_topic_is_not(self):
        byturn={x['source']['turn']:x for x in self.memories}
        self.assertTrue(engine.only_generic_overlap(byturn['D1:17'],byturn['D2:8']))
        self.assertFalse(engine.only_generic_overlap(byturn['D2:8'],byturn['D13:1']))
        rel={'from_id':byturn['D1:17']['memory_id'],'to_id':byturn['D2:8']['memory_id'],'type':'UPDATE','reason':'same activity'}
        states=[{'id':rel['from_id'],'state':'HISTORICAL'},{'id':rel['to_id'],'state':'ACTIVE'}]
        answers=[{'memories':states,'relations':[rel]},{'answer':'adoption agencies'}]
        with patch.object(engine,'vector',return_value=[byturn['D1:17'],byturn['D2:8']]),patch.object(engine,'lexical',return_value=[]),patch.object(engine,'generate',side_effect=answers):
            out=engine.answer('conv-26','What did Caroline research?','dynamic',2)
        self.assertEqual(out['relations'],[]);self.assertEqual(len(out['rejected_relations']),1)
    def test_relation_review_discards_unsupported_link(self):
        a,b=self.memories[:2]; rel={'from_id':a['memory_id'],'to_id':b['memory_id'],'type':'UPDATE','reason':'same topic'}
        states=[{'id':a['memory_id'],'state':'HISTORICAL'},{'id':b['memory_id'],'state':'ACTIVE'}]
        answers=[{'memories':states,'relations':[rel]},{'accepted':[],'rejected':[{'index':0,'reason':'insufficient evidence'}]},{'answer':'supported'}]
        with patch.object(engine,'vector',return_value=[a,b]),patch.object(engine,'lexical',return_value=[]),patch.object(engine,'generate',side_effect=answers):
            out=engine.answer('conv-26','question','dynamic',2)
        self.assertEqual(out['relations'],[])
        self.assertEqual(out['rejected_relations'][0]['review_reason'],'insufficient evidence')
        self.assertEqual(out['answer'],'supported')
    def test_dynamic_answer_uses_only_active_evidence(self):
        retrieved=self.memories[:3]
        states=[{'id':retrieved[0]['memory_id'],'state':'ACTIVE'}, {'id':retrieved[1]['memory_id'],'state':'HISTORICAL'}, {'id':retrieved[2]['memory_id'],'state':'IRRELEVANT'}]
        calls=[]
        def fake(prompt,json_mode):
            calls.append(prompt)
            return {'memories':states,'relations':[]} if len(calls)==1 else {'answer':'supported'}
        with patch.object(engine,'vector',return_value=retrieved),patch.object(engine,'lexical',return_value=[]),patch.object(engine,'generate',side_effect=fake):
            result=engine.answer('conv-26','test','dynamic',3)
        self.assertEqual(result['answer'],'supported')
        self.assertIn(retrieved[0]['memory_id'],calls[1])
        self.assertNotIn(retrieved[1]['memory_id'],calls[1])
        self.assertNotIn(retrieved[2]['memory_id'],calls[1])
    def test_relative_dates_use_session_date_without_fabricating_timezone(self):
        d19=next(x for x in self.memories if x['source']['turn']=='D19:1')
        match=[x for x in d19['resolved_time_expressions'] if x['expression'].lower()=='last friday']
        self.assertEqual(match[0]['date'],'2023-10-20')
        self.assertIn('timezone unknown',match[0]['basis'])
        self.assertEqual(engine.resolve_relative_dates('last month',d19['timestamp']),[])
        self.assertEqual(engine.resolve_relative_dates('feels like just yesterday I got married',d19['timestamp']),[])
        self.assertEqual(engine.resolve_relative_dates('last Friday','2:00 pm on 20 October, 2023')[0]['date'],'2023-10-13')
    def test_temporal_expression_is_checked_against_source(self):
        facts=[{'time_expression':'last Friday'},{'time_expression':'tomorrow'},{'time_expression':None}]
        result=engine.verify_fact_metadata(facts,'I went last Friday.')
        self.assertEqual([x['time_expression_in_source'] for x in result],[True,False,None])
    def test_extraction_refuses_missing_turns(self):
        with patch.object(engine,'generate',return_value={'items':[]}):
            with self.assertRaises(ValueError): extract.build(self.memories[:2])
    def test_failed_evaluations_remain_visible_in_score(self):
        result=evaluate.aggregate([{'method':'vector','answer_f1':1.0,'evidence_recall':1.0}, {'method':'vector','error':'failure'}])['vector']
        self.assertEqual(result['errors'],1)
        self.assertEqual(result['mean_answer_f1_success_only'],1.0)
        self.assertEqual(result['mean_answer_f1_errors_as_zero'],0.5)
    def test_extraction_rejects_duplicate_turns(self):
        turn=self.memories[0]['source']['turn']
        with patch.object(engine,'generate',return_value={'items':[{'turn':turn,'facts':[]},{'turn':turn,'facts':[]}]}):
            with self.assertRaises(ValueError): extract.build(self.memories[:1])
    def test_extraction_does_not_split_on_service_timeout(self):
        with patch.object(extract,'build',side_effect=TimeoutError('model busy')) as build:
            with self.assertRaises(TimeoutError): extract.build_resilient(self.memories[:3])
        self.assertEqual(build.call_count,1)
    def test_evaluation_excludes_unanswerable(self):
        q=[{'category':5,'adversarial_answer':'x'},{'category':1,'answer':'yes'},{'category':2,'answer':'a'}]
        self.assertEqual([i for i,_ in evaluate.select(q,0)],[1,2])
        self.assertEqual(evaluate.f1('a red ball','red ball'),1.0)
class HttpTests(unittest.TestCase):
    def test_import_endpoint_and_content_type(self):
        sample={'sample_id':'api-test','conversation':{'session_1_date_time':'1:00 pm on 1 May, 2023','session_1':[{'dia_id':'D1:1','speaker':'A','text':'hello'}]}}
        with tempfile.TemporaryDirectory() as directory,patch.object(engine,'IMPORT_DIR',Path(directory)),patch.object(engine,'DATA',[]):
            server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                url='http://127.0.0.1:'+str(server.server_port)+'/api/import';body=json.dumps(sample).encode()
                bad=urllib.request.Request(url,data=body,headers={'Content-Type':'text/plain'})
                with self.assertRaises(urllib.error.HTTPError) as err: urllib.request.urlopen(bad)
                self.assertEqual(err.exception.code,415)
                good=urllib.request.Request(url,data=body,headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(good) as response: self.assertEqual(json.load(response)['imported'],['api-test'])
                with self.assertRaises(urllib.error.HTTPError) as err: urllib.request.urlopen(good)
                self.assertEqual(err.exception.code,400)
            finally: server.shutdown();server.server_close()

if __name__=='__main__': unittest.main()
