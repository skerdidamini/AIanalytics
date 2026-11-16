import argparse
import hashlib
import os
from pathlib import Path
import secrets

from .database import Database


def main():
    parser=argparse.ArgumentParser(description='Analytics cloud API and offline credential provisioning')
    parser.add_argument('--database', required=True)
    commands=parser.add_subparsers(dest='command',required=True)
    serve=commands.add_parser('serve')
    serve.add_argument('--host',default='127.0.0.1')
    serve.add_argument('--port',type=int,default=8080)
    serve.add_argument('--ssl-certfile')
    serve.add_argument('--ssl-keyfile')
    for kind in ['provision-node','provision-reader']:
        command=commands.add_parser(kind)
        command.add_argument('--organization',required=True)
        command.add_argument('--token-file',required=True,help='New private file for generated credential; never printed')
        if kind=='provision-node':
            command.add_argument('--location',required=True)
            command.add_argument('--node',required=True)
            command.add_argument('--camera',action='append',required=True)
    revoke=commands.add_parser('revoke')
    revoke.add_argument('--token-file',required=True)
    args=parser.parse_args()
    path=Path(args.database).resolve()
    path.parent.mkdir(parents=True,exist_ok=True)
    database=Database(path)
    if args.command=='serve':
        import uvicorn
        from .app import create_app
        if bool(args.ssl_certfile)!=bool(args.ssl_keyfile):parser.error('Both TLS certificate and key are required')
        if args.host not in ('127.0.0.1','localhost','::1') and not args.ssl_certfile:
            parser.error('Use TLS for non-loopback listeners, or a loopback listener behind an HTTPS proxy')
        uvicorn.run(create_app(path),host=args.host,port=args.port,ssl_certfile=args.ssl_certfile,ssl_keyfile=args.ssl_keyfile,access_log=False,proxy_headers=False)
    elif args.command=='revoke':
        token=Path(args.token_file).read_text().strip()
        db=database.connect()
        try:
            with db: db.execute('UPDATE credentials SET revoked=1 WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
        finally:db.close()
        print('Credential revoked if present.')
    else:
        identifiers=[args.organization]
        if args.command=='provision-node':identifiers.extend([args.location,args.node,*args.camera])
        if any(not item.strip() or len(item)>128 for item in identifiers):parser.error('Identifiers require 1–128 characters')
        token=secrets.token_urlsafe(32)
        file=Path(args.token_file)
        fd=os.open(file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            with os.fdopen(fd,'w') as output:output.write(token+'\n')
            database.provision(args.organization,getattr(args,'location',None),getattr(args,'node',None),getattr(args,'camera',[]),token,
                               role='ingest' if args.command=='provision-node' else 'reader')
        except Exception:
            file.unlink(missing_ok=True)
            raise
        print('Credential generated in the specified private file; no credential value printed.')


if __name__=='__main__':main()
