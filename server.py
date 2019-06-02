import time

import json
import hashlib
from contextlib import asynccontextmanager as contextmanager
import asyncio

import websockets

from lenums import *

HOST = '0.0.0.0'
PORT = 61273

connections = {}

@contextmanager
async def con(s, p):
    if p not in connections:
        connections[p] = {'conns': set(), 'bg': None}
    pid = len(connections[p]['conns'])
    await s.send(json.dumps({'pid': pid, 'op': SockMsg.YOU}))
    if connections[p]['conns']:
        to_send = json.dumps({'pid': pid, 'op': SockMsg.ADD})
        await asyncio.wait([i.send(to_send) for i in connections[p]['conns']])
        await asyncio.wait([s.send(json.dumps({
            'pid': i, 'op': SockMsg.ADD
        })) for i in range(len(connections[p]))])
    if connections[p]['bg']:
        await s.send(json.dumps({
            'pid': 0, 'op': SockMsg.BAC, 'data': connections[p]['bg']
        }))
    connections[p]['conns'].add(s) #add after because the client creates itself
    try:
        yield pid
    finally:
        connections[p]['conns'].discard(s)
        to_send = json.dumps({'pid': pid, 'op': SockMsg.DEL})
        if connections[p]['conns']:
            await asyncio.wait([i.send(to_send) for i in connections[p]['conns']])
        else:
            del connections[p]

async def conn(ws, path):
    path = path.lstrip('/')
    if not path:
        newpath = hashlib.sha256(
            ', '.join(map(str, ws.remote_address)).encode()
        ).hexdigest()
        await ws.send(newpath)
        return
    print('connection opened', ws.remote_address)
    try:
        async with con(ws, path) as pid:
            async for msg in ws:
                deeta = json.loads(msg)
                if deeta['op'] == SockMsg.BAC and pid != 0:
                    continue
                if deeta['op'] == SockMsg.BAC:
                    connections[path]['bg'] = deeta['data']
                deeta['pid'] = pid
                msg = json.dumps(deeta)
                await asyncio.wait([s.send(msg)
                                    for s in connections[path]['conns']])
    finally:
        print('connection closed', ws.remote_address)

async def wakeup():
    while 1:
        await asyncio.sleep(1)

asyncio.get_event_loop().create_task(wakeup())
asyncio.get_event_loop().run_until_complete(
    websockets.serve(conn, HOST, PORT)
)
asyncio.get_event_loop().run_forever()
