from unittest import TestCase
from neosound.sound import *

#__all__ = ["create_sound",
#           "annotation",
#           "slicing",
#           ]
wavfile = "/auto/k8/tlee/songs/shaping_songs/Track1long.wav"

class SoundTest(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_create_sound(self):

        print("Loading sound from wavfile %s" % wavfile)
        s = Sound(wavfile)

        print("Creating white noise stimulus")
        s = Sound.whitenoise(duration=3*second)

        print("Creating tone stimulus")
        s = Sound.tone(duration=3*second, frequency=500*hertz)

        print("Creating pink noise stimulus")
        s = Sound.pinknoise(duration=3*second)

        return True

    def test_annotation(self):

        print("Creating a whitenoise stimulus")
        s = Sound.whitenoise(duration=3*second)
        print("Adding a bunch of annotations")
        s.annotate(name="whitenoise",
                   comment="This is a white noise stimulus",
                   noisiness="very",
                   annoyinglevel=10)
        assert s.annotations["name"] == "whitenoise"
        assert s.annotations["comment"] == "This is a white noise stimulus"
        assert s.annotations["noisiness"] == "very"
        assert s.annotations["annoyinglevel"] == 10

    def test_slicing(self):

        print("Creating sound from wavfile %s" % wavfile)
        s = Sound(wavfile)
        print("Extracting first 2 seconds of data")
        x = s[1*second: 3*second]
        assert x.duration == 2 * second
        # assert x[0] == s[0]
        # assert x[2 * second] == s[2 * second]
        assert x.start_time == 0 * second
        assert x.end_time == 2 * second
        assert x.annotations["original_start_time"] == 1 * second
        assert x.annotations["original_end_time"] == 3 * second

    def test_slicing_combined(self):

        print("Creating sound from wavfile %s" % wavfile)
        s = Sound(wavfile)
        print("Creating white noise")
        w = Sound.whitenoise(duration=s.duration, nchannels=s.nchannels, samplerate=s.samplerate)
        print("Combining sound with white noise")
        x = s[: 4 * second] + w[1 * second: 5 * second]
        print("Slicing combined sound")
        y = x[: 2 * second]
        assert y.ncomponents == 2
        assert y.components[0].start_time == 0 * second
        assert y.components[0].annotations["original_start_time"] == 0 * second
        assert y.components[0].annotations["original_end_time"] == 2 * second
        assert y.components[1].start_time == 0 * second
        assert y.components[1].annotations["original_start_time"] == 1 * second
        assert y.components[1].annotations["original_end_time"] == 3 * second



