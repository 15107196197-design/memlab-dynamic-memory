from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json, traceback, subprocess, os, sys
from pathlib import Path
import engine

class Handler(BaseHTTPRequestHandler):
    def send(self, value, status=200, content='application/json; charset=utf-8'):
        data=(json.dumps(value,ensure_ascii=False).encode('utf8') if content.startswith('application/json') else value.encode('utf8'))
        self.send_response(status); self.send_header('Content-Type',content); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        p=urlparse(self.path); args=parse_qs(p.query)
        try:
            if p.path=='/': self.send((engine.ROOT/'index.html').read_text(encoding='utf8'),content='text/html; charset=utf-8')
            elif p.path=='/api/samples': self.send([{'id':x['sample_id'],'split':next((k for k,v in engine.SPLIT.items() if x['sample_id'] in v),'imported'),'qa':len(x['qa'])} for x in engine.DATA])
            elif p.path=='/api/memories':
                s=next(x for x in engine.DATA if x['sample_id']==args.get('sample',[''])[0]); self.send(engine.memories(s))
            elif p.path=='/api/graphiti-demo':
                default_python=engine.ROOT.parent.parent.parent/'work'/'graphiti-env'/'Scripts'/'python.exe'
                python=os.getenv('GRAPHITI_PYTHON',str(default_python) if default_python.is_file() else sys.executable)
                completed=subprocess.run([python,str(engine.ROOT/'graphiti_demo.py')],capture_output=True,text=True,encoding='utf-8',timeout=30)
                if completed.returncode: raise RuntimeError('Graphiti 示例读取失败：'+completed.stderr.strip()[-600:])
                self.send(json.loads(completed.stdout))
            elif p.path=='/api/questions':
                s=next(x for x in engine.DATA if x['sample_id']==args.get('sample',[''])[0]); self.send(s['qa'])
            else: self.send({'error':'not found'},404)
        except Exception as e: self.send({'error':str(e)},400)
    def do_POST(self):
        try:
            if self.path not in ('/api/ask','/api/import'): return self.send({'error':'not found'},404)
            if self.headers.get('Content-Type','').split(';',1)[0].strip().lower()!='application/json': return self.send({'error':'Expected application/json'},415)
            length=int(self.headers.get('Content-Length','0'))
            limit=20_000_000 if self.path=='/api/import' else 100_000
            if length<=0 or length>limit: raise ValueError('Request size out of bounds')
            p=json.loads(self.rfile.read(length))
            if self.path=='/api/import': return self.send({'imported':engine.import_samples(p)})
            question=p['question'].strip()
            if not question: raise ValueError('Question required')
            self.send(engine.answer(p['sample'],question,p.get('method','dynamic'),min(50,max(1,int(p.get('k',15)))),p.get('as_of')))
        except (ValueError, KeyError, json.JSONDecodeError) as e: self.send({'error':str(e)},400)
        except Exception as e: traceback.print_exc(); self.send({'error':str(e)},500)

if __name__=='__main__':
    port=int(os.getenv('MEMORY_PORT','8765'))
    print(f'Open http://127.0.0.1:{port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
