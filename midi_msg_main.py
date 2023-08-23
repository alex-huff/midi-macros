import socket
import sys
import argparse
from ipc.protocol import getIPCSocketPath, sendMessage, readResponse, IPCIOError
from log.mm_logging import logError, exceptionStr

PROGRAM_NAME = "mm-msg"
VERSION = f"{PROGRAM_NAME} 0.0.1"
parser = argparse.ArgumentParser(
    prog=PROGRAM_NAME, description="IPC message client for midi-macros"
)
parser.add_argument(
    "-v",
    "--version",
    action="version",
    version=VERSION,
    help="show version number and exit",
)
parser.add_argument("-q", "--quiet", action="store_true", help="be quiet")
parser.add_argument("-s", "--socket", help="use alternative IPC socket path")
parser.add_argument("message", nargs="+")
args = parser.parse_args()

ipcSocket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
unixSocketPath = args.socket if args.socket else getIPCSocketPath()
try:
    ipcSocket.connect(unixSocketPath)
    sendMessage(ipcSocket, args.message)
    success, string = readResponse(ipcSocket)
    if not args.quiet:
        print(string)
    sys.exit(0 if success else -1)
except FileNotFoundError:
    logError(f"path: {unixSocketPath}, was not a valid file")
except PermissionError:
    logError(f"insufficient permissions to open file: {unixSocketPath}")
except IPCIOError as ipcIOError:
    logError(ipcIOError)
except Exception as exception:
    logError(f"failed to send message: {exceptionStr(exception)}")
finally:
    ipcSocket.close()
sys.exit(-1)
