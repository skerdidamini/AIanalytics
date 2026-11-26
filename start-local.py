"""Portable local dashboard bootstrap. Launch with Python 3.10+ from an extracted checkout."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description='Start AI Camera Analytica locally on this PC')
    parser.add_argument('--admin',action='store_true',help='Create/use the administrator account')
    parser.add_argument('--demo',action='store_true',help='Use isolated simulated data, never the real database')
    parser.add_argument('--port',type=int,default=8080)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    if sys.version_info<(3,10):raise SystemExit('Install Python 3.10 or newer (recommended: Python 3.12).')
    if not 1<=args.port<=65535:parser.error('Port must be between 1 and 65535')
    root=Path(__file__).resolve().parent
    project=root/'cloud'
    environment=project/'.venv'
    python=environment/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    if not python.exists():
        print('Preparing the local Python environment…',flush=True)
        subprocess.run([sys.executable,'-m','venv',str(environment)],check=True)
    signature=hashlib.sha256((project/'pyproject.toml').read_bytes()+str(project).encode()).hexdigest()
    marker=environment/'.local-dashboard-install'
    if not marker.exists() or marker.read_text()!=signature:
        print('Installing dependencies. Internet is required for the first setup…',flush=True)
        subprocess.run([str(python),'-m','pip','install','-e',str(project)],check=True)
        marker.write_text(signature)
    command=[str(python),'-m','cloud_api.local','--root',str(project),'--port',str(args.port)]
    if args.demo:command.append('--demo')
    if args.admin:command.append('--admin')
    if args.no_browser:command.append('--no-browser')
    return subprocess.call(command)


if __name__=='__main__':
    try:sys.exit(main())
    except KeyboardInterrupt:sys.exit(0)
    except (OSError,subprocess.CalledProcessError) as error:
        print('Local startup failed. Check Python installation and the messages above; no data was deleted.',file=sys.stderr)
        sys.exit(1)
