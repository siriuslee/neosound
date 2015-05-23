from __future__ import print_function
import os
import copy
from unittest import TestCase, main

import numpy as np

from neosound.sound import *

this_dir, this_filename = os.path.split(__file__)
wavfile = os.path.join(this_dir, "..", "..", "data", "zbsong.wav")
h5out = "/tmp/test.h5"

# TODO: Check that attributes are preserved in new objects (e.g. samplerate)
# TODO: Resample test
# TODO: Ramp test
# TODO: Filter test

def check_transform_data(func):
    
    transform_name = func.__name__.split("_")[1]

    def check_transform_storage(sound, original):

        try:
            metadata = sound.manager.database.get_metadata(sound.id)
            assert len(metadata) > 0
        except AssertionError:
            print("Failed")
            raise
        else:
            print("Passed")

    def check_transform_reconstruct(sound, original):

        try:
            new_sound = sound.manager.reconstruct(sound.id)
            assert np.all(np.asarray(sound) == np.asarray(new_sound))
        except AssertionError:
            print("Failed")
            raise
        else:
            print("Passed")

    def wrapfunc(obj):
        print("Checking %s transform..." % transform_name, end="")
        try:
            result, original = func(obj)
        except AssertionError:
            print("Failed")
            raise
        else:
            print("Passed")

        print("Checking %s transform storage..." % transform_name, end="")
        check_transform_storage(result, original)

        print("Checking %s transform reconstruction..." % transform_name, end="")
        check_transform_reconstruct(result, original)

    return wrapfunc

class SoundTransformTest(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def check_metadata(self, sound):
        attributes = ["id", "annotations"]

        for attribute in attributes:
            assert hasattr(sound, attribute)

    def test_create_transform(self):

        # Should check that these types are what we say they are.
        print("Checking white noise stimulus creation...", end="")
        try:
            sound = Sound.whitenoise(duration=3*second)
            self.check_metadata(sound)
        except AssertionError:
            print("Failed")
            raise
        else:
            print("Passed")

        print("Checking tone stimulus creation...", end="")
        try:
            sound = Sound.tone(duration=3*second, frequency=500*hertz)
            self.check_metadata(sound)
        except AssertionError:
            print("Failed")
            raise
        else:
            print("Passed")

        print("Checking pink noise stimulus creation...", end="")
        try:
            sound = Sound.pinknoise(duration=3*second)
            self.check_metadata(sound)
        except AssertionError:
            print("Failed")
            raise
        else:
            print("Passed")

        return True

    def test_load_transform(self):

        print("Checking sound loading...", end="")
        try:
            sound = Sound(wavfile)
            self.check_metadata(sound)
            assert "original_filename" in sound.annotations
        except AssertionError:
            print("Failed")
            raise
        else:
            print("Passed")

    @check_transform_data
    def test_mono_transform(self):

        sound = Sound.whitenoise(duration=3*second, nchannels=2)
        assert sound.nchannels == 2
        mono = sound.to_mono()
        assert mono.nchannels == 1

        return mono, sound

    @check_transform_data
    def test_pad_transform(self):

        sound = Sound.whitenoise(duration=3*second)
        assert sound.nsamples == int(3*second * sound.samplerate)
        padded = sound.pad(duration=5*second)
        assert padded.nsamples == int(5*second * sound.samplerate)

        return padded, sound

    @check_transform_data
    def test_clip_transform(self):

        sound = Sound.whitenoise(duration=3*second)
        clip_to = float(np.abs(sound).max()) * 0.8
        clipped = sound.clip(clip_to, -clip_to)
        inds = np.abs(np.asarray(clipped)) < clip_to
        assert np.all(np.asarray(clipped)[inds] == np.asarray(sound)[inds])
        assert np.all(np.abs(np.asarray(clipped))[~inds] == clip_to)

        return clipped, sound

    @check_transform_data
    def test_slice_transform(self):

        sound = Sound.whitenoise(duration=3*second)
        sliced = sound.slice(1*second, 3*second)
        assert sliced.nsamples == int(2*second * sound.samplerate)
        assert sliced[0] == sound[int(1*second * sound.samplerate)]
        assert sliced[-1] == sound[-1]

        return sliced, sound

    @check_transform_data
    def test_multiply_transform(self):

        sound = Sound.whitenoise(duration=3*second)
        scaled = sound.set_level(70 * dB)
        assert np.all(np.isclose(scaled.level, 70))

        return scaled, sound

    @check_transform_data
    def test_add_transform(self):

        sound1 = Sound.whitenoise(duration=3*second)
        sm = sound1.manager
        sound2 = Sound.whitenoise(duration=3*second, manager=sm)
        combined = sound1.combine(sound2)
        assert np.all(np.asarray(combined) == (np.asarray(sound1) + np.asarray(sound2)))

        return combined, (sound1, sound2)

    @check_transform_data
    def test_set_transform(self):

        sound1 = Sound.whitenoise(duration=3*second)
        sm = sound1.manager
        sound2 = Sound.whitenoise(duration=1*second)
        replaced = sound1.replace(0*second, 1*second, sound2)
        assert np.all(np.asarray(replaced[:1*second]) == np.asarray(sound2))
        assert np.all(np.asarray(replaced[1*second:]) == np.asarray(sound1[1*second:]))

        return replaced, (sound1, sound2)

    @check_transform_data
    def test_component_transform(self):

        s = Sound(wavfile).to_mono()
        w = Sound.whitenoise(duration=s.duration + 1*second,
                             samplerate=s.samplerate,
                             nchannels=1)
        c = s.embed(w, start=0.5*second, ratio=0*dB)
        c1 = c.component(0)
        assert np.all(c1.slice(0.5*second, 0.5*second+s.duration).asarray() == s.asarray())
        # c1.store()

        return c1, s


if __name__ == "__main__":

    main()