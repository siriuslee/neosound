from unittest import TestCase
import numpy as np
from neosound.sound import *

wavfile = "/auto/k8/tlee/songs/shaping_songs/Track1long.wav"
h5out = "/tmp/test.h5"


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

    # def test_annotation(self):
    #
    #     print("Creating a whitenoise stimulus")
    #     s = Sound.whitenoise(duration=3*second)
    #     print("Adding a bunch of annotations")
    #     s.annotate(name="whitenoise",
    #                comment="This is a white noise stimulus",
    #                noisiness="very",
    #                annoyinglevel=10)
    #     assert s.annotations["name"] == "whitenoise"
    #     assert s.annotations["comment"] == "This is a white noise stimulus"
    #     assert s.annotations["noisiness"] == "very"
    #     assert s.annotations["annoyinglevel"] == 10

    def test_slicing(self):

        print("Creating sound from wavfile %s" % wavfile)
        s = Sound(wavfile)
        print("Extracting 2 seconds of data")
        x = s[1*second: 3*second]
        assert x.duration == 2 * second
        assert x[0] == s[1*second]
        assert x[2*second] == s[3*second]

    def test_dict_storage(self):

        print("Testing if sound is given an id")
        s = Sound(wavfile)
        assert hasattr(s, "id")

        print("Testing if metadata is stored")
        assert len(s.manager.database.get_metadata(s.id)) > 0

        print("Testing if root nodes can be obtained")
        w = Sound.whitenoise(duration=2*second)
        t = Sound.tone(duration=2*second, frequency=1000*hertz)
        x = w + t
        s[:x.duration] = x
        root_ids = s.manager.get_roots(s.id)
        for test_id in [s.id, w.id, t.id]:
            assert test_id in root_ids

        print("Testing if a sound can be reconstructed")
        y = x.manager.reconstruct(x.id)
        assert np.equal(x, y)

        print("Testing if a sound component can be reconstructed")
        y = s.component(root_ids.index(w.id))
        assert np.equal(y, w)






