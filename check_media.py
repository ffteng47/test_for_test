import asyncio
import json
import sys
import urllib.request

import websockets

async def main():
    try:
        with urllib.request.urlopen('http://127.0.0.1:9222/json/list', timeout=5) as r:
            targets = json.loads(r.read().decode())
        page = next(t for t in targets if 'pan.quark.cn' in t.get('url', ''))
        ws = page['webSocketDebuggerUrl']
        expr = '(function(){const arr=[];document.querySelectorAll("video,audio,source").forEach(e=>{if(e.src) arr.push(e.src);});return arr.slice(0,3).join("||");})()'
        async with websockets.connect(ws) as conn:
            await conn.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
            await conn.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': expr}}))
            async for msg in conn:
                d = json.loads(msg)
                if d.get('id') == 2:
                    try:
                        print(d['result']['result'].get('value', ''))
                    except Exception:
                        print('')
                    return 0
        return 1
    except Exception as e:
        print('ERR', e)
        return 1

if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
