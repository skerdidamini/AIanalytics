"""Bound request bodies before framework model parsing, including chunked requests."""
class RequestSizeLimit:
    def __init__(self,app,max_bytes=1024*1024):self.app,self.max_bytes=app,max_bytes

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        body=bytearray()
        while True:
            message=await receive()
            if message['type']=='http.disconnect':return
            if message['type']!='http.request':continue
            chunk=message.get('body',b'')
            if len(body)+len(chunk)>self.max_bytes:
                result=b'{"detail":"Request too large"}'
                await send({'type':'http.response.start','status':413,'headers':[(b'content-type',b'application/json'),(b'content-length',str(len(result)).encode())]})
                await send({'type':'http.response.body','body':result});return
            body.extend(chunk)
            if not message.get('more_body',False):break
        delivered=False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered=True
                return {'type':'http.request','body':bytes(body),'more_body':False}
            return await receive()
        await self.app(scope,replay,send)
