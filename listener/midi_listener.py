import time
from threading import RLock
from rtmidi.midiutil import open_midiinput
from rtmidi._rtmidi import (
    InvalidPortError,
    SystemError as RTMIDISystemError,
    NoDevicesError,
)
from aspn import aspn
from log.mm_logging import loggingContext, logInfo, exceptionStr
from macro.matching import numNotesInTrigger, testTriggerWithPlayedNotes
from listener.played_note import PlayedNote
from listener.subprofile_holder import SubprofileHolder
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
from script.argument import MIDI_MESSAGE_FORMAT_MESSAGE_BYTES_HEX
from midi.midi_message import MIDIMessage
from midi.constants import *


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
        self.pedalDown = [False for _ in range(16)]
        self.virtualPedalDown = False
        self.hadExtraMessageSincePress = False
        self.enabled = True
        self.portName = None
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
            if not self.virtualPedalDown:
                self.handleSustainRelease()
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

    def getInfo(self):
        with self.listenerLock:
            return {
                "enabled": self.enabled,
                "midi-input": self.portName,
                "sustain": self.pedalDown,
                "virtual-sustain": self.virtualPedalDown,
                "subprofiles": (
                    self.subprofileHolder.getInfo() if self.subprofileHolder else None
                ),
            }

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
        with self.listenerLock, loggingContext(self.profile):
            self.handleMIDIEvent(event)

    def handleSustainRelease(self):
        def shouldRelease(nc):
            if not self.pedalDown[nc[1]]:
                toRelease.add(nc)
                return True
            return False

        toRelease = set()
        self.queuedReleases = {
            nc for nc in self.queuedReleases if not shouldRelease(nc)
        }
        if len(toRelease) > 0:
            if self.lastChangeWasAdd:
                self.executeMacros()
                self.lastChangeWasAdd = False
            self.pressed = [
                pn
                for pn in self.pressed
                if (pn.getNote(), pn.getChannel()) not in toRelease
            ]

    def handleMIDIEvent(self, event):
        message, _ = event
        if not message:
            return
        message = MIDIMessage(message, time.time_ns())
        self.executeMacros(message)
        statusType = message.getStatus()
        channel = message.getChannel()
        data_1 = message.getData1()
        data_2 = message.getData2()
        shouldIgnore = (
            statusType != NOTE_ON
            and statusType != NOTE_OFF
            and (statusType != CONTROL_CHANGE or data_1 != SUSTAIN_PEDAL)
        )
        if shouldIgnore:
            if statusType not in (POLY_PRESSURE, CHANNEL_PRESSURE):
                self.hadExtraMessageSincePress = True
            return
        wasSustainingOnChannel = self.pedalDown[channel] or self.virtualPedalDown
        if statusType == CONTROL_CHANGE:
            self.pedalDown[channel] = data_2 >= 64
            isSustainingOnChannel = self.pedalDown[channel] or self.virtualPedalDown
            if wasSustainingOnChannel and not isSustainingOnChannel:
                self.handleSustainRelease()
            return
        isSustainingOnChannel = wasSustainingOnChannel
        velocity = data_2
        note = data_1
        wasPress = statusType == NOTE_ON and velocity > 0
        nc = (note, channel)
        if wasPress:
            if nc in self.queuedReleases:
                self.queuedReleases.remove(nc)
            self.pressed.append(PlayedNote(note, channel, velocity, time.time_ns()))
            self.hadExtraMessageSincePress = False
        else:
            if isSustainingOnChannel:
                self.queuedReleases.add(nc)
                return
            else:
                if self.lastChangeWasAdd:
                    self.executeMacros()
                self.pressed = [
                    pn
                    for pn in self.pressed
                    if pn.getNote() != note or pn.getChannel() != channel
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
        if self.enabled and self.testTrigger(
            self.cycleSubprofilesTrigger, self.cycleSubprofilesTriggerLength
        ):
            self.cycleSubprofiles()
            return True
        return False

    def executeMacros(self, midiMessage=None):
        with loggingContext(self.profile):
            if (not midiMessage and self.handleTriggers()) or not self.enabled:
                return
            midiMessageSpecifier = (
                f" with MIDI message: {MIDI_MESSAGE_FORMAT_MESSAGE_BYTES_HEX.convert(midiMessage)}"
                if midiMessage
                else ""
            )
            logInfo(
                f"evaluating pressed keys: {' '.join(f'{playedNote.getChannel()}:{aspn.midiNoteToASPN(playedNote.getNote())}' for playedNote in self.pressed) if self.pressed else None}{midiMessageSpecifier}"
            )
            self.globalMacroTree.executeMacros(self.pressed, self.hadExtraMessageSincePress, midiMessage)
            if not self.subprofileHolder:
                return
            self.subprofileHolder.executeMacros(self.pressed, self.hadExtraMessageSincePress, midiMessage)

    def run(self):
        with loggingContext(self.profile):
            self.queueToggleCallback()
            self.queueVirtualSustainCallback()
            self.queueSubprofileCallback()
            self.openMIDIPort()

    def openMIDIPort(self):
        try:
            self.midiin, self.portName = open_midiinput(
                self.config[MIDI_INPUT], interactive=False
            )
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
        with loggingContext(self.profile):
            if not hasattr(self, "midiin"):
                return
            # rtmidi internally will interrupt and join with callback thread
            logInfo("closing midi port")
            self.midiin.close_port()
            del self.midiin
            logInfo("waiting for queued script invocations to complete")
            self.globalMacroTree.shutdown()
            if self.subprofileHolder:
                self.subprofileHolder.shutdown()
