# midi-macros
midi-macros allows you to run scripts triggered by actions from a MIDI capable device. This effectively turns a MIDI controller (such as an [AKAI MPK mini](https://www.akaipro.com/mpk-mini-mk3)) into a [Stream Deck](https://www.elgato.com/us/en/s/welcome-to-stream-deck). Types of actions include playing a note, playing a chord, playing a sequence of notes and chords, and other MIDI events such as turning a knob or moving a slider.

To somebody comfortable with scripting, a MIDI controller with midi-macros is far more flexible than devices like the [Stream Deck](https://www.elgato.com/us/en/s/welcome-to-stream-deck) since press velocity, analog controls (knobs or sliders), multi-key sequences, chords, channels, sustain, and basically anything else MIDI has to offer, can be used to better define macros. Arguments can even be passed into scripts to modify its function based on extra notes played, or other MIDI events like those genererated by turning a knob. This enables complex uses cases like changing volume and brightness where analog hardware controls do better than a keyboard or [Stream Deck](https://www.elgato.com/us/en/s/welcome-to-stream-deck). midi-macros allows for multiple MIDI devices to be used at once using device profiles, and device profiles can have subprofiles that have different sets of macros depending on your current use case. Device profiles also have a set of global macros that are always present regardless of which subprofile is selected.

## Macro Examples
Open xterm when middle C is pressed:
```
C4 → xterm

# same as above but channel must be 0
C4{c==0} → xterm
```

Open xterm when a middle C major chord is played:
```
C4+E4+G4 → xterm

# same as above but all notes must be played on channel 0
(C4+E4+G4){c==0} → xterm

# you can specify chords by surrounding a set of notes in brackets, seperating them with |
# this allows you to play C4, E4, G4 in any order
[C4|E4|G4] → xterm

# same as above but all notes must be played on channel 0
([C4|E4|G4]){c==0} → xterm
```

You can also chain together notes and chords, and specify other requirements
```
# in the following macro:
# A3, B3, C3 can be played in any order
# B3 must be on channel 6
# D5 must come after A3, B3, C3, and must have a velocity >=64
# C6 must come after D5 and be on channel 7
[A3|B3{c==6}|C3]+D5{v>=64}+C6{c==7} → xterm

# in the following macro:
# B4 must have been pressed at least 2 seconds after A4 (et is elapsed time)
# the elapsed time (difference in time between first and last note press) of the C4, E4, G4 chord must be <= 4 seconds (cet is chord elapsed time)
# all notes must have been played on channel 0
(
    A4+
    B4{sec(et)>=2}+
    [C4|E4|G4]{sec(cet)<=4}
){c==0} → xterm
```

Using arguments
```
# here, the ASPN of any extra notes played after C4 are passed into the script through STDIN
# for example, playing C4+D4+E4 would output `D4 E4` since cat reads STDIN and dumps it to STDOUT
# ASPN is American Standard Pitch Notation (example: C4, F♯5)
C4 *(ASPN) → cat

# this macro does the same thing as the one above, but:
# it will only be executed if there are 1-4 extra notes played
# arguments are not passed over STDIN, they replace the substring `{}` in the script
# MIDI values are used instead of ASPN
# `-` is used to seperate arguments instead of a space
C4 *[1:4]("{}"→[-]MIDI) → echo {}

# instead of using a predefined argument format like ASPN or MIDI, you can use a python f-string format

# this macro, for 1 or more extra notes after C4:
# outputs the MIDI value, the ASPN, the piano key number, the velocity, and the time the note was pressed in seconds since epoch
# seperates each argument with a newline
C4 *[1:]("{}"→["\n"]f"MIDI: {m}, ASPN: {a}, PIANO: {p}, VELOCITY: {v}, TIME: {sec(playedNote.getTime())}") → echo "{}"
```
