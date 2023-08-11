# midi-macros
midi-macros allows you to run scripts triggered by actions from a MIDI capable device. This effectively turns a MIDI controller (such as an [AKAI MPK mini](https://www.akaipro.com/mpk-mini-mk3)) into a [Stream Deck](https://www.elgato.com/us/en/s/welcome-to-stream-deck) on steroids. Types of actions include playing a note, playing a chord, playing a sequence of notes and chords, and other MIDI events such as turning a knob or moving a slider.

To somebody comfortable with scripting, midi-macros is far more flexible than hardware like the [Stream Deck](https://www.elgato.com/us/en/s/welcome-to-stream-deck) since press velocity, analog controls (knobs or sliders), multi-key sequences, chords, channels, sustain, and basically anything else MIDI has to offer, can be used to better define macros. Arguments can even be passed into scripts to modify its function based on extra notes played, or other MIDI events like those genererated by turning a knob. This enables complex uses cases like changing volume and brightness where analog hardware controls do better than a keyboard or [Stream Deck](https://www.elgato.com/us/en/s/welcome-to-stream-deck). midi-macros allows for multiple MIDI devices to be used at once using device profiles, and device profiles can have subprofiles that have different sets of macros depending on your current use case. Device profiles also have a set of global macros that are always present regardless of which subprofile is selected.

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

# for this macro, the order in which you play C4, E4, G4 does not matter
[C4|E4|G4] → xterm

# same as above but all notes must be played on channel 0
([C4|E4|G4]){c==0} → xterm
```

You can also chain together notes and chords, and specify velocity requirements
```
# A3, B3, C3 can be played in any order
# B3 must be on channel 6
# D5 must come after A3, B3, C3, and must have a velocity >=64
# C6 must come after D5 and be on channel 7
[A3|B3{c==6}|C3]+D5{v>=64}+C6{c==7} → xterm
```

Control cmus music player
```
# cmus control with pads on MPK mini
# on the MPK mini, pads are on channel 9
# MIDI value 40-43 are used instead of E2-G2, but either would work
40{c==9} → cmus-remote --pause
41{c==9} → cmus-remote --prev
42{c==9} → cmus-remote --next
43{c==9} → cmus-remote -C "toggle repeat_current"
```
