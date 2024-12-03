#!/bin/python3

import os
import io
import socket
import struct
import json

from collections.abc import Buffer


def read_message(sock: socket.socket):
    message_header_buffer = bytearray(message_header_struct.size)
    recv_all(sock, message_header_buffer)
    magic_bytes, payload_length, payload_type = \
        message_header_struct.unpack(message_header_buffer)
    assert magic_bytes == MAGIC
    payload_buffer = bytearray(payload_length)
    recv_all(sock, payload_buffer)
    return json.loads(payload_buffer.decode("utf-8"))


def recv_all(sock: socket.socket, buffer: Buffer):
    buffer_memory_view = memoryview(buffer)
    bytes_received = 0
    while bytes_received < len(buffer):
        bytes_received += sock.recv_into(
            buffer_memory_view[bytes_received:])


def send_message(sock: socket.socket, payload_type: int, payload: Buffer):
    sock.sendall(
        message_header_struct.pack(MAGIC, len(payload), payload_type))
    sock.sendall(payload)


def subscribe(sock: socket.socket, event_types: list[str]) -> None:
    json_string = json.dumps(event_types)
    send_message(sock, SUBSCRIBE_MESSAGE_TYPE, json_string.encode("utf-8"))
    response = read_message(sway_sock)
    assert response["success"]


MAGIC = b"i3-ipc"
SUBSCRIBE_MESSAGE_TYPE = 2
WORKSPACE_EVENT_TYPE = 0x80000000
MODE_EVENT_TYPE = 0x80000002
WINDOW_EVENT_TYPE = 0x80000003

message_header_struct = struct.Struct(f"={len(MAGIC)}sII")
sway_sock_path = os.environ["SWAYSOCK"]
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sway_sock:
    sway_sock.connect(sway_sock_path)
    relevant_events = [
        "workspace",
        "mode",
        "window",
    ]
    subscribe(sway_sock, relevant_events)
    while True:
        print(read_message(sway_sock))
