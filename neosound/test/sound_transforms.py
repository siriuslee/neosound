from __future__ import print_function
import os
import copy
from unittest import TestCase

import numpy as np

from neosound.sound import *

this_dir, this_filename = os.path.split(__file__)
wavfile = os.path.join(this_dir, "..", "..", "data", "zbsong.wav")
h5out = "/tmp/test.h5"


class SoundTransformTest(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def check_transform(self, transform_name, sound):

        print("Checking %s transform storage..." % transform_name, end="")
        self.check_transform_storage(sound)

        print("Checking %s transform reconstruction..." % transform_name, end="")
        self.check_transform_reconstruct(sound)

    def check_metadata(self, sound):
        attributes = ["id", "annotations", "transformation"]

        for attribute in attributes:
            assert hasattr(sound, attribute)

    def check_transform_storage(self, sound):

        try:
            metadata = sound.manager.database.get_metadata(sound.id)
            assert len(metadata) > 0
        except AssertionError:
            print("Failed")
        else:
            print("Passed")

    def check_transform_reconstruct(self, sound):

        try:
            new_sound = sound.manager.reconstruct(sound.id)
            assert np.all(np.asarray(sound) == np.asarray(new_sound))
        except AssertionError:
            print("Failed")
        else:
            print("Passed")

    def test_create_transform(self):

        print("Checking white noise stimulus creation...", end="")
        try:
            sound = Sound.whitenoise(duration=3*second)
            self.check_metadata(sound)
        except AssertionError:
            print("Failed")
        else:
            print("Passed")

        print("Checking tone stimulus creation...", end="")
        try:
            sound = Sound.tone(duration=3*second, frequency=500*hertz)
            self.check_metadata(sound)
        except AssertionError:
            print("Failed")
        else:
            print("Passed")

        print("Checking pink noise stimulus creation...", end="")
        try:
            sound = Sound.pinknoise(duration=3*second)
            self.check_metadata(sound)
        except AssertionError:
            print("Failed")
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
        else:
            print("Passed")

    def test_mono_transform(self):

        print("Checking mono transform...", end="")
        sound = Sound.whitenoise(duration=3*second, nchannels=2)
        try:
            assert sound.nchannels == 2
            assert sound.to_mono().nchannels == 1
        except AssertionError:
            print("Failed")
            return
        else:
            print("Passed")

        self.check_transform("mono", sound)

    def test_pad_transform(self):

        print("Checking pad transform...", end="")
        sound = Sound.whitenoise(duration=3*second)
        try:
            assert sound.nsamples == int(3*second * sound.samplerate)
            sound = sound.pad(duration=5*second)
            assert sound.nsamples == int(5*second * sound.samplerate)
        except AssertionError:
            print("Failed")
            return
        else:
            print("Passed")

        self.check_transform("pad", sound)

    def test_clip_transform(self):

        print("Checking clip transform...", end="")
        sound = Sound.whitenoise(duration=3*second)
        try:
            assert sound.max() > 0.25
            assert sound.min() < -0.25
            sound = sound.clip(-0.25, 0.25)
            assert sound.max() == 0.25
            assert sound.min() == -0.25
        except AssertionError:
            print("Failed")
            return
        else:
            print("Passed")

        self.check_transform("clip", sound)

    def test_slice_transform(self):

        print("Checking slice transform...", end="")
        sound = Sound.whitenoise(duration=3*second)
        try:
            sliced = sound[1*second: 3*second]
            assert sliced.nsamples == int(2*second * sound.samplerate)
            assert sliced[0] == sound[1*second]
            assert sliced[-1] == sound[-1]
        except AssertionError:
            print("Failed")
            return
        else:
            print("Passed")

        self.check_transform("slice", sliced)

    def test_multiply_transform(self):

        print("Checking multiply transform...", end="")
        sound = Sound.whitenoise(duration=3*second)
        try:
            new_sound = 2 * sound
            assert np.all(np.asarray(sound) * 2 == np.asarray(new_sound))
        except AssertionError:
            print("Failed")
            return
        else:
            print("Passed")

        self.check_transform("multiply", new_sound)

    def segfaulting_inplace_multiply_transform(self):

        print("Checking in-place multiply transform...", end="")
        sound = Sound.whitenoise(duration=3*second)
        copy_sound = copy.deepcopy(sound)
        try:
            sound *= 2
            assert sound.id != copy_sound.id
            assert np.all(np.asarray(sound) == 2 * np.asarray(copy_sound))
        except AssertionError:
            print("Failed")
            return
        else:
            print("Passed")

        self.check_transform("in-place multiply", sound)

    def test_add_transform(self):

        print("Checking add transform...", end="")
        sound1 = Sound.whitenoise(duration=3*second)
        sm = sound1.manager
        sound2 = Sound.whitenoise(duration=3*second, manager=sm)
        try:
            combined_sound = sound1 + sound2
            assert np.all(np.asarray(combined_sound) == (np.asarray(sound1) + np.asarray(sound2)))
        except AssertionError:
            print("Failed")
            return
        else:
            print("Passed")

        self.check_transform("add", combined_sound)

    def test_set_transform(self):

        print("Checking set transform...", end="")
        sound1 = Sound.whitenoise(duration=3*second)
        sm = sound1.manager
        sound2 = Sound.whitenoise(duration=1*second)
        try:
            new_sound = sound1
            new_sound[:1*second] = sound2
            assert np.all(np.asarray(new_sound[:1*second]) == np.asarray(sound2))
            assert np.all(np.asarray(new_sound[1*second:]) == np.asarray(sound1[1*second:]))
        except AssertionError:
            print("Failed")
            return
        else:
            print("Passed")

        self.check_transform("set", new_sound)
