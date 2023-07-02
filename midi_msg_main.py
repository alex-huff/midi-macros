import socket
import sys
import argparse
from ipc.ipc_utils import getIPCSocketPath, sendMessage, readString

VERSION='0.0.1'
parser = argparse.ArgumentParser(
    prog='mm-msg',
    description='IPC message client for midi-macros'
)
parser.add_argument('-v', '--version', action='store_true', help='show version number')
parser.add_argument('-q', '--quiet', action='store_true', help='be quiet')
parser.add_argument('-s', '--socket', help='alternative IPC socket path')
parser.add_argument('message', nargs='+')
args = parser.parse_args()

if (args.version):
    print(VERSION)
    sys.exit(1)
ipcSocket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
unixSocketPath = args.socket if args.socket else getIPCSocketPath()
try:
    ipcSocket.connect(unixSocketPath)
    sendMessage(ipcSocket, args.message)
    response = readString(ipcSocket)
    if (not args.quiet):
        print(response)
except FileNotFoundError:
    print(f'ERROR: path: {unixSocketPath} was not a valid file', file=sys.stderr)
    sys.exit(-1)
except PermissionError:
    print(f'ERROR: insufficient permissions to open file: {unixSocketPath}', file=sys.stderr)
    sys.exit(-1)
except:
    print(f'ERROR: failed to connect to socket: {unixSocketPath}', file=sys.stderr)
    sys.exit(-1)
finally:
    ipcSocket.close()
