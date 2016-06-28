from __future__ import print_function
from unittest import TestCase, main
import logging

import numpy as np

from neosound.sound import *

this_dir, this_filename = os.path.split(__file__)
wavfile = os.path.join(this_dir, "..", "..", "data", "zbsong.wav")

class SoundManagerTest(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_roots(self):

        print("Checking that roots are correct...", end="")
        s = Sound(wavfile)
        w = Sound.whitenoise(duration=s.duration + 1*second,
                             samplerate=s.samplerate,
                             nchannels=s.nchannels)
        n = s.slice(1*second, 3*second).set_level(65*dB)
        c = n.embed(w, start=0.5*second, ratio=0*dB)

        roots = c.roots
        try:
            assert s.id in roots
            assert w.id in roots
        except AssertionError:
            print("Failed")
            raise
        else:
            print("Passed")

    def test_import_ids(self):

        print("Checking that data imports between managers...", end="")
        manager = SoundManager(DictStore)
        # manager.logger.setLevel(logging.DEBUG)
        s = Sound(wavfile, manager=manager)
        w = Sound.whitenoise(duration=s.duration + 1*second,
                             samplerate = s.samplerate,
                             nchannels = s.nchannels,
                             manager=manager)
        n = s.slice(1*second, 3*second).set_level(65*dB)
        c = n.embed(w, start=0.5*second, ratio=0*dB)

        # Test simple import
        simple_manager = SoundManager(DictStore)
        ids = [w.id]
        simple_ids = simple_manager.import_ids(manager, ids, foo="bar", reconstruct_necessary=False)

        # Test reconstruction
        recon_manager = SoundManager(DictStore)
        ids = [c.id]
        recon_ids = recon_manager.import_ids(manager, ids)

        # Test recursive import
        recurse_manager = SoundManager(DictStore)
        ids = [c.id]
        recurse_ids = recurse_manager.import_ids(manager, ids, recursive=True)

        try:
            # Check simple
            metadata = manager.database.get_metadata(w.id)
            i_metadata = simple_manager.database.get_metadata(simple_ids[0])
            for key, val in metadata.iteritems():
                if key not in ["children", "parents"]:
                    assert (key in i_metadata) and (i_metadata[key] == val)
            annotations = manager.database.get_annotations(w.id)
            i_annotations = simple_manager.database.get_annotations(simple_ids[0])
            for key, val in annotations.iteritems():
                assert (key in i_annotations) and (i_annotations[key] == val)
            assert ("foo" in i_annotations) and (i_annotations["foo"] == "bar")

            # Check reconstruction
            assert recon_manager.database.get_data(recon_ids[0]) is not None
            assert np.all(c.asarray() == recon_manager.reconstruct(recon_ids[0]).asarray())

            # Check recursive
            is_parent = lambda x:True
            parents = manager.database.filter_by_func(transform_children=is_parent)
            i_parents = recurse_manager.database.filter_by_func(transform_children=is_parent)
            assert len(parents) ==  len(i_parents)
        except AssertionError:
            print("Failed")
            raise
        else:
            print("Passed")

if __name__ == "__main__":

    main()