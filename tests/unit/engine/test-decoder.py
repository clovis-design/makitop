import time

from makitop.playback.clock import PlaybackClock


clock = PlaybackClock()

print("Début :", clock.current_time())

clock.play()

time.sleep(2)

print("Après 2 secondes :", clock.current_time())

clock.pause()

print("Pause :", clock.current_time())

time.sleep(2)

print("Toujours en pause :", clock.current_time())

clock.seek(10)

print("Après seek :", clock.current_time())

clock.stop()

print("Après stop :", clock.current_time())