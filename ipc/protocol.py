import os
import tempfile

XDG_RUNTIME_DIR = "XDG_RUNTIME_DIR"


class IPCIOError(Exception):
    def __init__(self, message):
        self.message = message


def getIPCSocketPath():
    xdgRuntimeDir = os.environ.get(XDG_RUNTIME_DIR)
    if xdgRuntimeDir:
        unixSocketDirPath = xdgRuntimeDir
    else:
        unixSocketDirPath = tempfile.gettempdir()
    return os.path.join(unixSocketDirPath, "midi-macros-ipc.sock")


def sendMessage(ipcSocket, message):
    messageLength = len(message)
    sendVarInt(ipcSocket, messageLength)
    for string in message:
        sendString(ipcSocket, string)


def sendResponse(ipcSocket, response):
    success, string = response
    successInt = 0x1 if success else 0x0
    sendVarInt(ipcSocket, successInt)
    sendString(ipcSocket, string)


def sendString(ipcSocket, string):
    stringBytes = string.encode()
    stringBytesLen = len(stringBytes)
    sendVarInt(ipcSocket, stringBytesLen)
    sendall(ipcSocket, stringBytes)


def sendVarInt(ipcSocket, uInt):
    varIntBytes = bytearray()
    continuationBit = 0x80
    while continuationBit:
        lowSeven = uInt & 0x7F
        uInt >>= 7
        continuationBit = continuationBit if uInt else 0
        varIntByte = continuationBit | lowSeven
        varIntBytes.append(varIntByte)
    sendall(ipcSocket, varIntBytes)


def readMessage(ipcSocket):
    numStrings = readVarInt(ipcSocket)
    return [readString(ipcSocket) for _ in range(numStrings)]


def readResponse(ipcSocket):
    return (bool(readVarInt(ipcSocket)), readString(ipcSocket))


def readString(ipcSocket):
    stringSize = readVarInt(ipcSocket)
    return recvall(ipcSocket, stringSize).decode()


def readVarInt(ipcSocket):
    continuationBit = 0x80
    varInt = 0
    bytesProcessed = 0
    while continuationBit:
        byte = recvall(ipcSocket, 1)[0]
        continuationBit = byte & continuationBit
        byte = byte & 0x7F
        varInt |= byte << (7 * bytesProcessed)
        bytesProcessed += 1
    return varInt


def sendall(ipcSocket, toSend):
    ipcSocket.sendall(toSend)


def recvall(ipcSocket, toRead):
    data = bytearray(toRead)
    view = memoryview(data)
    while toRead:
        bytesRead = ipcSocket.recv_into(view, toRead)
        if not bytesRead:
            raise IPCIOError("connection closed unexpectedly while reading")
        view = view[bytesRead:]
        toRead -= bytesRead
    return data
