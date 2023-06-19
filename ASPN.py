import math

octavePositionToPitch = ['C', 'C#', 'D', 'D#',
                         'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
pitchToOctavePosition = {
    'C': 0,
    'D': 2,
    'E': 4,
    'F': 5,
    'G': 7,
    'A': 9,
    'B': 11,
}


def midiNoteToASPN(note):
    octave = math.floor((note - 12) / 12)
    pitch = octavePositionToPitch[(note - 12) % 12]
    return f'{pitch}{octave}'


def aspnOctaveBasePitchOffsetToMIDI(octave, basePitch, offset):
    return octave * 12 + 12 + pitchToOctavePosition[basePitch] + offset
