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
        self.subprofileHolder = SubprofileHolder(
            self.profile, subprofiles) if subprofiles else None
        self.globalMacroTree = self.config[GLOBAL_MACROS]
        self.listenerLock = RLock()
        self.pressed = []
        self.queuedReleases = set()
        self.lastChangeWasAdd = False
        self.pedalDown = [False for _ in range(16)]
        self.virtualPedalDown = False
        self.enabled = True
        self.portName = None
        self.enableTrigger = self.config.get(ENABLE_TRIGGER)
        self.enableTriggerLength = (
            numNotesInTrigger(
                self.enableTrigger) if self.enableTrigger else None
        )
        self.cycleSubprofilesTrigger = self.config.get(
            CYCLE_SUBPROFILES_TRIGGER)
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

    def getInfo(self):
        with self.listenerLock:
            return {
                "enabled": self.enabled,
                "midi-input": self.portName,
                "sustain": self.pedalDown,
                "virtual-sustain": self.virtualPedalDown,
                "subprofiles": self.subprofileHolder.getInfo() if self.subprofileHolder else None,
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
        with self.listenerLock:
            self.handleUpdate(event)

    def handleSustainRelease(self, channel):
        def shouldRelease(nc):
            if nc[1] == channel:
                toRelease.add(nc[0])
                return True
            return False
        toRelease = set()
        self.queuedReleases = {
            nc for nc in self.queuedReleases if not shouldRelease(nc)}
        if len(toRelease) > 0:
            if self.lastChangeWasAdd:
                self.executeMacros()
                self.lastChangeWasAdd = False
            self.pressed = [pn for pn in self.pressed if pn.getChannel() != channel or pn.getNote()
                            not in toRelease]

    def handleUpdate(self, event, virtualSustainToggleUpdate=False):
        if virtualSustainToggleUpdate:
            for channel in range(16):
                wasSustainingOnChannel = self.pedalDown[channel] or not self.virtualPedalDown
                isSustainingOnChannel = self.pedalDown[channel] or self.virtualPedalDown
                if wasSustainingOnChannel and not isSustainingOnChannel:
                    self.handleSustainRelease(channel)
            return
        eventData, _ = event
        if len(eventData) < 3:
            return
        (status, data_1, data_2) = eventData
        statusType = status >> 4
        channel = status & 0xF
        if (
            statusType != NOTE_ON_STATUS
            and statusType != NOTE_OFF_STATUS
            and (statusType != CONTROL_CHANGE_STATUS or data_1 != SUSTAIN_PEDAL)
        ):
            return
        wasSustainingOnChannel = self.pedalDown[channel] or self.virtualPedalDown
        if statusType == CONTROL_CHANGE_STATUS:
            self.pedalDown[channel] = data_2 >= 64
            isSustainingOnChannel = self.pedalDown[channel] or self.virtualPedalDown
            if wasSustainingOnChannel and not isSustainingOnChannel:
                self.handleSustainRelease(channel)
            return
        isSustainingOnChannel = wasSustainingOnChannel
        velocity = data_2
        note = data_1
        wasPress = statusType == NOTE_ON_STATUS and velocity > 0
        nc = (note, channel)
        if wasPress:
            if nc in self.queuedReleases:
                self.queuedReleases.remove(nc)
            self.pressed.append(PlayedNote(
                note, channel, velocity, time.time_ns()))
        else:
            if isSustainingOnChannel:
                self.queuedReleases.add(nc)
                return
            else:
                if self.lastChangeWasAdd:
                    self.executeMacros()
                self.pressed = [pn for pn in self.pressed if pn.getNote() !=
                                note or pn.getChannel() != channel]
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
            self.midiin, self.portName = open_midiinput(
                self.config[MIDI_INPUT], interactive=False
            )
            self.midiin.set_callback(self)
        except InvalidPortError:
            raise ListenerException(
                f"invalid midi port: {self.config[MIDI_INPUT]}")
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
        logInfo('closing midi port', profile=self.profile)
        self.midiin.close_port()
        del self.midiin
        logInfo('waiting for queued script invocations to complete',
                profile=self.profile)
        self.globalMacroTree.shutdown()
        if self.subprofileHolder:
            self.subprofileHolder.shutdown()
