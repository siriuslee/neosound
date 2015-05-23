from __future__ import print_function
from unittest import TestCase, main
import os

import numpy as np

from neosound.sound_store import *
from neosound.sound_transforms import SoundTransform


def check_storage(func):

    store_name = " ".join(func.__name__.split("_")[1:-1])

    def wrapfunc(obj):

        # Test storage
        print("Checking %s storage..." % store_name, end="")
        try:
            func(obj)
        except AssertionError:
            print("Failed")
            raise
        else:
            print("Passed")

    return wrapfunc

class SoundStoreTest(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    # def test_dictionary_store(self):
    #
    #     pass

    @check_storage
    def test_hdf5_store(self):

        filename = os.tempnam() + ".h5"
        # Create a store
        store = HDF5Store(filename, read_only=False)

        # Create a new id_
        id_ = store.get_id()

        # Test store annotation
        assert store.store_annotations(id_, foo="bar", foo2="bar2")
        annotations = store.get_annotations(id_)
        assert (annotations["foo"] == "bar") and \
               (annotations["foo2"] == "bar2")

        # Test store metadata
        assert store.store_metadata(id_, type=SoundTransform, parents=["parent1"])
        metadata = store.get_metadata(id_)
        assert (metadata["type"] == SoundTransform) and \
               (metadata["parents"] == ["parent1"])

        # Test store data
        assert store.store_data(id_, np.zeros((500, 2)))
        data = store.get_data(id_)
        assert np.all(data == 0) and data.shape == (500, 2)

    @check_storage
    def test_hdf5_read_only_store(self):

        filename = os.tempnam() + ".h5"
        # Create a store
        store = HDF5Store(filename)
        store.read_only = True

        # Create a new id_
        id_ = store.get_id()

        # Test store annotation
        assert store.store_annotations(id_, foo="bar", foo2="bar2") == False
        assert id_ not in store.list_ids()

        # Test store metadata
        assert store.store_metadata(id_, type=SoundTransform) == False

        # Test store data
        assert store.store_data(id_, np.zeros((500, 2))) == False

        # Check create group
        assert store._get_group(store.filename, store.get_id()) == False


if __name__ == "__main__":

    main()
