import os

XDG_RUNTIME_DIR = 'XDG_RUNTIME_DIR'
UNIX_TEMP_DIR = 'TMPDIR'


class MessageFormatError(Exception):
    def __init__(self, message):
        self.message = message

    def getMessage(self):
        return self.message


def getIPCSocketPath():
    if (XDG_RUNTIME_DIR in os.environ):
        unixSocketDirPath = os.environ[XDG_RUNTIME_DIR]
    elif (UNIX_TEMP_DIR in os.environ):
        unixSocketDirPath = os.environ[UNIX_TEMP_DIR]
    else:
        unixSocketDirPath = '/tmp'
    return os.path.join(unixSocketDirPath, 'midi-macros-ipc.sock')


def sendMessage(ipcSocket, message):
    messageLength = len(message)
    if (messageLength > 255):
        raise MessageFormatError(
            f'message was too long: {messageLength} (>255) strings')
    sendUnsignedInt(ipcSocket, messageLength)
    for string in message:
        sendString(ipcSocket, string)


def sendString(ipcSocket, string):
    stringBytes = string.encode()
    stringBytesLen = len(stringBytes)
    if (stringBytesLen > 255):
        raise MessageFormatError(
            f'encoded string: {string} was too big: {stringBytesLen} (>255) bytes')
    sendUnsignedInt(ipcSocket, stringBytesLen)
    sendall(ipcSocket, stringBytes)


def sendUnsignedInt(ipcSocket, uInt, size=1):
    sendall(ipcSocket, uInt.to_bytes(size))


def readMessage(ipcSocket):
    numStrings = readUnsignedInt(ipcSocket)
    return [readString(ipcSocket) for _ in range(numStrings)]


def readString(ipcSocket):
    stringSize = readUnsignedInt(ipcSocket)
    return recvall(ipcSocket, stringSize).decode()


def readUnsignedInt(ipcSocket, size=1):
    return int.from_bytes(recvall(ipcSocket, size))


def sendall(ipcSocket, toSend):
    ipcSocket.sendall(toSend)


def recvall(ipcSocket, toRead):
    data = bytearray(toRead)
    view = memoryview(data)
    while (toRead):
        bytesRead = ipcSocket.recv_into(view, toRead)
        if (not bytesRead):
            raise IOError()
        view = view[bytesRead:]
        toRead -= bytesRead
    return data
