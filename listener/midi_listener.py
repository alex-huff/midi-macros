import subprocess
import time
from threading import RLock, Thread, Event
from queue import Queue, Empty
from rtmidi.midiutil import open_midiinput
from rtmidi._rtmidi import (
    InvalidPortError,
    SystemError as RTMIDISystemError,
    NoDevicesError,
)
from aspn import aspn
from log.mm_logging import logError, logInfo, exceptionStr
from macro.matching import numNotesInTrigger, testTriggerWithPlayedNotes
from parser.parser import ParseError, parseMacroFile
from listener.played_note import PlayedNote
from midi.constants import *
from config.mm_config import (
    MACRO_FILE,
    MIDI_INPUT,
    TOGGLE_TRIGGER,
    TOGGLE_CALLBACK,
    VIRTUAL_SUSTAIN_CALLBACK,
    DEBOUNCE_CALLBACKS,
    CALLBACK_TYPES
)


class ListenerException(Exception):
    def __init__(self, message):
        self.message = message


class MidiListener:
    def __init__(self, profileName, config):
        self.profileName = profileName
        self.config = config
        self.listenerLock = RLock()
        self.pressed = []
        self.queuedReleases = set()
        self.lastChangeWasAdd = False
        self.pedalDown = False
        self.virtualPedalDown = False
        self.enabled = True
        self.toggleTrigger = self.config.get(TOGGLE_TRIGGER)
        self.toggleTriggerLength = (
            numNotesInTrigger(self.toggleTrigger) if self.toggleTrigger else None
        )
        self.toggleCallback = self.config.get(TOGGLE_CALLBACK)
        self.virtualSustainCallback = self.config.get(VIRTUAL_SUSTAIN_CALLBACK)
        self.callbackQueue = Queue()
        self.callbackThread = Thread(target=self.executeCallbacksForever, daemon=True)
        self.terminateEvent = Event()

    def executeCallbacksForever(self):
        while not self.terminateEvent.wait(timeout=1 / 50):
            callbacks = []
            try:
                while True:
                    callbacks.append(self.callbackQueue.get_nowait())
            except Empty:
                pass
            if len(callbacks) == 0:
                continue
            if self.config[DEBOUNCE_CALLBACKS]:
                for callbackType in CALLBACK_TYPES:
                    callbacksOfType = [callback for callback in callbacks if callback[0] == callbackType]
                    if len(callbacksOfType) > 0:
                        self.executeCallback(*callbacksOfType[-1][1:])
            else:
                for callback in callbacks:
                    self.executeCallback(*callback[1:])
            for _ in range(len(callbacks)):
                self.callbackQueue.task_done()

    def executeCallback(self, callback, message):
        try:
            subprocess.Popen(
                callback,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                shell=True,
            ).communicate(message)
        except Exception as exception:
            logError(
                f"failed to run callback, {exceptionStr(exception)}",
                self.profileName,
            )

    def toggleEnabled(self):
        with self.listenerLock:
            self.enabled = not self.enabled
            self.queueToggleCallback()
            return self.enabled

    def setEnabled(self, enabled):
        with self.listenerLock:
            if self.enabled == enabled:
                return
            self.toggleEnabled()

    def toggleVirtualPedalDown(self):
        with self.listenerLock:
            self.virtualPedalDown = not self.virtualPedalDown
            self.handleUpdate(None, virtualSustainToggleUpdate=True)
            self.queueVirtualSustainCallback()
            return self.virtualPedalDown

    def setVirtualPedalDown(self, down):
        with self.listenerLock:
            if self.virtualPedalDown == down:
                return
            self.toggleVirtualPedalDown()

    def queueToggleCallback(self):
        if self.toggleCallback:
            self.callbackQueue.put(
                (
                    TOGGLE_CALLBACK,
                    self.toggleCallback,
                    f"{self.profileName} {'enabled' if self.enabled else 'disabled'}",
                )
            )

    def queueVirtualSustainCallback(self):
        if self.virtualSustainCallback:
            self.callbackQueue.put(
                (
                    VIRTUAL_SUSTAIN_CALLBACK,
                    self.virtualSustainCallback,
                    f"sustain {'enabled' if self.virtualPedalDown else 'disabled'}",
                )
            )

    def __call__(self, event, data=None):
        with self.listenerLock:
            self.handleUpdate(event)

    def handleSustainRelease(self):
        if self.lastChangeWasAdd and len(self.queuedReleases) > 0:
            self.executeMacros()
            self.lastChangeWasAdd = False
        self.pressed = [
            playedNote
            for playedNote in self.pressed
            if playedNote.getNote() not in self.queuedReleases
        ]
        self.queuedReleases.clear()

    def handleUpdate(self, event, virtualSustainToggleUpdate=False):
        if virtualSustainToggleUpdate:
            wasSustaining = self.pedalDown or not self.virtualPedalDown
            isSustaining = self.pedalDown or self.virtualPedalDown
            if wasSustaining and not isSustaining:
                self.handleSustainRelease()
            return
        eventData, _ = event
        if len(eventData) < 3:
            return
        (status, data_1, data_2) = eventData
        if (
            status != NOTE_ON_STATUS
            and status != NOTE_OFF_STATUS
            and (status != CONTROL_CHANGE_STATUS or data_1 != SUSTAIN_PEDAL)
        ):
            return
        wasSustaining = self.pedalDown or self.virtualPedalDown
        if status == CONTROL_CHANGE_STATUS:
            self.pedalDown = data_2 > 0
            isSustaining = self.pedalDown or self.virtualPedalDown
            if wasSustaining and not isSustaining:
                self.handleSustainRelease()
            return
        isSustaining = wasSustaining
        velocity = data_2
        note = data_1
        wasPress = status == NOTE_ON_STATUS and velocity > 0
        if wasPress:
            if note in self.queuedReleases:
                self.queuedReleases.remove(note)
            self.pressed.append(PlayedNote(note, velocity, time.time_ns()))
        else:
            if isSustaining:
                self.queuedReleases.add(note)
                return
            else:
                if self.lastChangeWasAdd:
                    self.executeMacros()
                self.pressed = [
                    playedNote
                    for playedNote in self.pressed
                    if playedNote.getNote() != note
                ]
        self.lastChangeWasAdd = wasPress

    def executeMacros(self):
        if (
            self.toggleTrigger
            and self.toggleTriggerLength == len(self.pressed)
            and testTriggerWithPlayedNotes(
                self.pressed, self.toggleTrigger, self.toggleTriggerLength
            )
        ):
            self.toggleEnabled()
            return
        if not self.enabled:
            return
        logInfo(
            f"evaluating pressed keys: {[aspn.midiNoteToASPN(playedNote.getNote()) for playedNote in self.pressed]}",
            self.profileName,
        )
        self.macroTree.executeMacros(self.pressed)

    def run(self):
        self.initializeMacros()
        self.queueToggleCallback()
        self.queueVirtualSustainCallback()
        self.openMIDIPort()
        self.callbackThread.start()

    def initializeMacros(self):
        macroFilePath = self.config[MACRO_FILE]
        try:
            with open(macroFilePath, "r") as macroFile:
                self.macroTree = parseMacroFile(macroFile, self.profileName)
        except ParseError as parseError:
            raise ListenerException(parseError.message)
        except (FileNotFoundError, IsADirectoryError):
            raise ListenerException(f"invalid macro file: {macroFilePath}")
        except PermissionError:
            raise ListenerException(
                f"insufficient permissions to open macro file: {macroFilePath}"
            )
        except Exception as exception:
            raise ListenerException(
                f"could not open macro file: {macroFilePath}, {exceptionStr(exception)}"
            )

    def openMIDIPort(self):
        try:
            self.midiin, _ = open_midiinput(self.config[MIDI_INPUT], interactive=False)
            self.midiin.set_callback(self)
        except InvalidPortError:
            raise ListenerException(f"invalid midi port: {self.config[MIDI_INPUT]}")
        except RTMIDISystemError:
            raise ListenerException("MIDI system error")
        except NoDevicesError:
            raise ListenerException("no MIDI devices")
        except Exception as exception:
            raise ListenerException(
                f"could not open midi port: {self.config[MIDI_INPUT]}, {exceptionStr(exception)}"
            )

    def stop(self):
        if not hasattr(self, "midiin"):
            return
        # rtmidi internally will interrupt and join with callback thread
        self.midiin.close_port()
        del self.midiin
        self.callbackQueue.join()
        self.terminateEvent.set()
        self.callbackThread.join()
