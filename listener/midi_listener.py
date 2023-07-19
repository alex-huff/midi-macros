import time
from threading import RLock
from rtmidi.midiutil import open_midiinput
from rtmidi._rtmidi import (
    InvalidPortError,
    SystemError as RTMIDISystemError,
    NoDevicesError,
)
from aspn import aspn
from log.mm_logging import logInfo, exceptionStr
from macro.matching import numNotesInTrigger, testTriggerWithPlayedNotes
from listener.played_note import PlayedNote
from listener.subprofile_holder import SubprofileHolder
from midi.constants import *
from callback.callback import Callback
from config.mm_config import (
    MIDI_INPUT,
    ENABLE_TRIGGER,
    CYCLE_SUBPROFILES_TRIGGER,
    ENABLE_CALLBACK,
    VIRTUAL_SUSTAIN_CALLBACK,
    SUBPROFILE_CALLBACK,
    SUBPROFILES,
    GLOBAL_MACROS,
)


class ListenerException(Exception):
    def __init__(self, message):
        self.message = message


class MidiListener:
    def __init__(self, profile, config, callbackQueue):
        self.profile = profile
        self.config = config
        self.callbackQueue = callbackQueue
        subprofiles = self.config[SUBPROFILES]
        self.subprofileHolder = SubprofileHolder(subprofiles) if subprofiles else None
        self.globalMacroTree = self.config[GLOBAL_MACROS]
        self.listenerLock = RLock()
        self.pressed = []
        self.queuedReleases = set()
        self.lastChangeWasAdd = False
        self.pedalDown = False
        self.virtualPedalDown = False
        self.enabled = True
        self.enableTrigger = self.config.get(ENABLE_TRIGGER)
        self.enableTriggerLength = (
            numNotesInTrigger(self.enableTrigger) if self.enableTrigger else None
        )
        self.cycleSubprofilesTrigger = self.config.get(CYCLE_SUBPROFILES_TRIGGER)
        self.cycleSubprofilesTriggerLength = (
            numNotesInTrigger(self.cycleSubprofilesTrigger)
            if self.cycleSubprofilesTrigger
            else None
        )
        self.enableCallback = self.config.get(ENABLE_CALLBACK)
        self.virtualSustainCallback = self.config.get(VIRTUAL_SUSTAIN_CALLBACK)
        self.subprofileCallback = self.config.get(SUBPROFILE_CALLBACK)

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

    def cycleSubprofiles(self):
        if not self.subprofileHolder:
            return
        with self.listenerLock:
            subprofileChanged = self.subprofileHolder.cycle()
            if subprofileChanged:
                self.queueSubprofileCallback()
            return self.subprofileHolder.getCurrent()

    def setSubprofile(self, subprofile):
        if not self.subprofileHolder:
            return
        with self.listenerLock:
            subprofileChanged = self.subprofileHolder.setCurrent(subprofile)
            if subprofileChanged:
                self.queueSubprofileCallback()
            return self.subprofileHolder.getCurrent()

    def getSubprofiles(self):
        if not self.subprofileHolder:
            return ()
        return self.subprofileHolder.getNames()

    def booleanCallbackMessage(self, enabled):
        return f"{'enabled' if enabled else 'disabled'}"

    def queueToggleCallback(self):
        if self.enableCallback:
            self.callbackQueue.put(
                Callback(
                    self.profile,
                    ENABLE_CALLBACK,
                    self.enableCallback,
                    self.booleanCallbackMessage(self.enabled),
                )
            )

    def queueVirtualSustainCallback(self):
        if self.virtualSustainCallback:
            self.callbackQueue.put(
                Callback(
                    self.profile,
                    VIRTUAL_SUSTAIN_CALLBACK,
                    self.virtualSustainCallback,
                    self.booleanCallbackMessage(self.virtualPedalDown),
                )
            )

    def queueSubprofileCallback(self):
        if self.subprofileHolder and self.subprofileCallback:
            self.callbackQueue.put(
                Callback(
                    self.profile,
                    SUBPROFILE_CALLBACK,
                    self.subprofileCallback,
                    self.subprofileHolder.getCurrent(),
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
        # print(eventData, _)
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
            self.pedalDown = data_2 >= 64
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

    def testTrigger(self, trigger, triggerLength):
        return (
            trigger
            and triggerLength == len(self.pressed)
            and testTriggerWithPlayedNotes(self.pressed, trigger, triggerLength)
        )

    def handleTriggers(self):
        if self.testTrigger(self.enableTrigger, self.enableTriggerLength):
            self.toggleEnabled()
            return True
        if self.testTrigger(
            self.cycleSubprofilesTrigger, self.cycleSubprofilesTriggerLength
        ):
            self.cycleSubprofiles()
            return True
        return False

    def executeMacros(self):
        if self.handleTriggers() or not self.enabled:
            return
        logInfo(
            f"evaluating pressed keys: {[aspn.midiNoteToASPN(playedNote.getNote()) for playedNote in self.pressed]}",
            self.profile,
        )
        self.globalMacroTree.executeMacros(self.pressed)
        if not self.subprofileHolder:
            return
        self.subprofileHolder.getCurrentMacroTree().executeMacros(self.pressed)

    def run(self):
        self.queueToggleCallback()
        self.queueVirtualSustainCallback()
        self.queueSubprofileCallback()
        self.openMIDIPort()

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
