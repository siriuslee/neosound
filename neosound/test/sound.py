from __future__ import print_function
import os
import copy
from unittest import TestCase, main

import numpy as np

from neosound.sound import *

this_dir, this_filename = os.path.split(__file__)
wavfile = os.path.join(this_dir, "..", "..", "data", "zbsong.wav")
h5out = "/tmp/test.h5"


class SoundTest(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_annotation(self):

        print("Checking annotations...", end="")
        s = Sound.whitenoise(duration=3*second)

        try:
            s.annotate(name="whitenoise",
                       comment="This is a white noise stimulus",
                       noisiness="very",
                       annoyinglevel=10)
            assert s.annotations["name"] == "whitenoise"
            assert s.annotations["comment"] == "This is a white noise stimulus"
            assert s.annotations["noisiness"] == "very"
            assert s.annotations["annoyinglevel"] == 10
        except AssertionError:
            print("Failed")
            raise
        else:
            print("Passed")


if __name__ == "__main__":

    main()