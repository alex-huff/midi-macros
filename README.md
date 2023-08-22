# midi-macros
## About
midi-macros allows you to run scripts triggered by actions from a MIDI capable device. This effectively turns a MIDI controller (such as an [AKAI MPK mini](https://www.akaipro.com/mpk-mini-mk3)) into a [Stream Deck](https://www.elgato.com/us/en/s/welcome-to-stream-deck). Types of actions include playing a note, playing a chord, playing a sequence of notes and chords, and other MIDI events such as turning a knob or moving a slider.

To somebody comfortable with scripting, a MIDI controller with midi-macros is far more flexible than devices like the [Stream Deck](https://www.elgato.com/us/en/s/welcome-to-stream-deck) since press velocity, analog controls (knobs or sliders), multi-key sequences, chords, channels, sustain, and basically anything else MIDI has to offer, can be used to better define macros. Arguments can even be passed into scripts to modify its function based on extra notes played, or other MIDI events like those genererated by turning a knob. This enables complex uses cases like changing volume and brightness where analog hardware controls do better than a keyboard or [Stream Deck](https://www.elgato.com/us/en/s/welcome-to-stream-deck).

midi-macros allows for multiple MIDI devices to be used at once using device profiles, and device profiles can have subprofiles that have different sets of macros depending on your current use case. Device profiles also have a set of global macros that are always present regardless of which subprofile is selected.

## Macro Examples
### Simple
Open xterm when middle C is pressed
```
C4 → xterm

# same as above but channel must be 0
C4{c==0} → xterm
```

Open xterm when a middle C major chord is played
```
C4+E4+G4 → xterm

# same as above but all notes must be played on channel 0
(C4+E4+G4){c==0} → xterm

# you can specify chords by surrounding a set of notes in brackets, seperating them with |
# this allows you to play C4, E4, G4 in any order
[C4|E4|G4] → xterm

# same as above but all notes must be played on channel 0
[C4|E4|G4]{c==0} → xterm
```
### Complicated
Here are some examples of how I use midi-macros:

Controlling volumes with knobs
```
# main volume with knob 1
MIDI{STATUS==cc}{CC_FUNCTION==70}("{}"→CC_VALUE_PERCENT) [BLOCK|DEBOUNCE]→ pactl set-sink-volume @DEFAULT_SINK@ {}%

# cmus volume with knob 2
MIDI{STATUS==cc}{CC_FUNCTION==71}("{}"→CC_VALUE_PERCENT) [BLOCK|DEBOUNCE]→ cmus-remote --volume {}%

# control focused application volume with knob 3
# this solution is built for use with sway
MIDI{STATUS==cc}{CC_FUNCTION==72}("{}"→f"{CC_VALUE_SCALED(0, 1)}") (python)[BLOCK|DEBOUNCE]→
{
	import subprocess
	focused_pid = int(
		subprocess.check_output(
			"swaymsg -t get_tree | jq '.. | select(.type?) | select(.focused==true).pid'",
			text=True,
			shell=True
		)
	)
	import psutil
	focused_process = psutil.Process(focused_pid)
	process_hierarchy = {p.pid for p in focused_process.children(recursive=True)}
	process_hierarchy.add(focused_pid)
	import pulsectl
	pid_property = "application.process.id"
	with pulsectl.Pulse("mm-pulseaudio-client") as pulse:
		for sink_input in pulse.sink_input_list():
			sink_input_pid = sink_input.proplist.get(pid_property)
			if sink_input_pid and int(sink_input_pid) in process_hierarchy:
				pulse.volume_set_all_chans(sink_input, {})
				break
}
```

Controlling cmus
```
40{c==9} → cmus-remote --pause
41{c==9} → cmus-remote --prev
42{c==9} → cmus-remote --next
43{c==9} → cmus-remote -C "toggle repeat_current"

# seek current song with knob
C3 MIDI{STATUS==cc}{CC_FUNCTION==72}("{}"→CC_VALUE) [BLOCK|DEBOUNCE]→
{
	current_song_duration=$(cmus-remote -Q | grep duration | cut -d " " -f 2)
	cmus-remote --seek $(python -c "print(round(({} / 127) * $current_song_duration))")
}
```

Controlling the brightness of a smart light with HomeAssistant
```
MIDI{STATUS==cc}{CC_FUNCTION==77}("{}"→f"{round(CC_VALUE_SCALED(0, 255))}") [BLOCK|DEBOUNCE]→
{
	hass-cli service call --arguments "entity_id=light.color_lights,brightness={}" light.turn_on
}
```

Switching between subprofiles with rofi
```
48{c==9} →
{
	profile="MPK mini"
	subprofile=$(mm-msg profile "$profile" get-loaded-subprofiles | rofi -dmenu)
	mm-msg profile "$profile" set-subprofile "$subprofile"
}
```
