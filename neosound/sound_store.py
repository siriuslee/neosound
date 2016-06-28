import copy
import os
import uuid
from functools import wraps

import h5py
import os

from neosound import sound_transforms


# TODO: abstract SoundStore class to bring more to the parent class
# TODO: Document dictionary and HDF5 storage
# TODO: add MongoDB storage


def writes(func):
    """
    All methods that might write to the database should be wrapped with this function. If the read-only flag of the store is set to True, this function will raise an error.
    :param func: function to wrap
    :return: wrapped function
    """

    @wraps(func)
    def writeok(obj, *args, **kwargs):

        if obj.read_only:
            return False
            # raise IOError("SoundStore object is set as read-only. Cannot write!")
        else:
            return func(obj, *args, **kwargs)

    return writeok


class SoundStore(object):
    """
    Base sound storage class.
    """

    def __init__(self, filename=None, read_only=False):

        self.filename = filename
        self.read_only = read_only

    @staticmethod
    def get_id():

        return str(uuid.uuid4())


class DictStore(SoundStore):

    def __init__(self, *args, **kwargs):
        """
        Provides a dictionary-backed sound storage. This is a non-persistent form of storage, as the dictionary is never written out to disk.
        :param read_only: flag to prevent writing to the database. (False)
        """

        read_only = kwargs.get("read_only", False)
        super(DictStore, self).__init__(read_only=read_only)
        self.data = dict()

    def get_annotations(self, id_):
        """
        Get the annotations for the specified sound
        :param id_: sound id
        :return: A dictionary of annotations.
        """

        annotations = dict((key, value) for key, value in self.data[id_].iteritems() if not (key.startswith("transform_") or (key == "waveform")))

        return annotations

    def get_metadata(self, id_):
        """
        Get the transformation metadata for the specified sound
        :param id_: sound id
        :return: a dictionary of transformation metadata
        """

        metadata = dict()
        for key, val in self.data[id_].iteritems():
            if key.startswith("transform_"):
                key = key.split("transform_")[1]
                if key == "type":
                    val = getattr(sound_transforms, val)
                metadata[key] = val

        return metadata

    def get_data(self, id_):
        """
        Get the waveform data for the specified sound if stored
        :param id_: sound id
        :return: a numpy array or None if it doesn't exist
        """

        if "waveform" in self.data[id_]:
            return self.data[id_]["waveform"]

    @writes
    def store_annotations(self, id_, **kwargs):

        self.data.setdefault(id_, dict()).update(kwargs)

        return True

    @writes
    def store_metadata(self, id_, **kwargs):

        if "type" in kwargs:
            kwargs["type"] = kwargs["type"].__name__
        metadata = dict([("transform_" + key, value) for key, value in kwargs.iteritems()])
        self.data.setdefault(id_, dict()).update(metadata)

        return True

    @writes
    def store_data(self, id_, data):

        self.data.setdefault(id_, dict())["waveform"] = data

        return True

    def filter_ids(self, ids=None, num_matches=None, **kwargs):

        result_ids = list()
        if ids is None:
            ids = self.data.iterkeys()
        for name in ids:
            annotations = self.data[name]
            match = True
            for key, value in kwargs.iteritems():
                if key in annotations:
                    if annotations[key] != value:
                        match = False
                        break
                else:
                    match = False
                    break
            if match:
                result_ids.append(name)

            if (num_matches is not None) and (len(result_ids) == num_matches):
                break

        return result_ids

    def filter_by_func(self, ids=None, num_matches=None, **kwarg_funcs):

        result_ids = list()
        if ids is None:
            ids = self.data.iterkeys()
        for name in ids:
            annotations = self.data[name]
            match = True
            for key, func in kwarg_funcs.iteritems():
                if key in annotations:
                    if not func(annotations[key]):
                        match = False
                        break
                else:
                    match = False
                    break
            if match:
                result_ids.append(name)

            if (num_matches is not None) and (len(result_ids) == num_matches):
                break

        return result_ids

    def list_ids(self):

        return self.data.keys()

    def list_roots(self):

        return self.filter_by_func(transform_parents=lambda x: len(x) == 0)


class HDF5Store(SoundStore):

    #TODO Dictionary-like get and set methods?
    #TODO Store metadata about the different annotations throughout the file so that filtering can be done much faster.

    def __init__(self, filename, *args, **kwargs):
        """
        Provides HDF5 file backed sound storage.
        :param filename: filename for HDF5 file. If it does not exist, it will be created.
        :param read_only: flag to prevent writing to the database. (False)
        """

        read_only = kwargs.get("read_only", False)
        super(HDF5Store, self).__init__(filename, read_only)

        # Initialize the file if it doesn't exist
        # If the file is read_only, should I even create it?
        if not os.path.exists(self.filename):
            if not self.read_only:
                with h5py.File(self.filename, "a") as f:
                    pass
            else:
                raise IOError("File %s cannot be opened read-only. It does not exist!" % self.filename)


    def _get_group(self, f, group_name):

        if group_name in f:
            g = f[group_name]
        else:
            if self.read_only:
                g = False
            else:
                g = f.create_group(group_name)
        return g

    def get_annotations(self, id_, ds=None):

        id_ = unicode(id_)
        with h5py.File(self.filename, "r") as f:
            g = self._get_group(f, id_)
            if g:
                if ds is not None:
                    if ds in g:
                        g = g[ds]
                    else:
                        raise KeyError("Requested annotations for unknown dataset %s" % str(ds))
                annotations = dict([(key, value) for key, value in g.attrs.iteritems() if not key.startswith("transform_")])
                return annotations
            else:
                raise KeyError("Requested data for id %s doesn't exist!" % id_)

    def get_metadata(self, id_):

        id_ = unicode(id_)
        with h5py.File(self.filename, "r") as f:
            g = self._get_group(f, id_)
            if g:
                metadata = dict()
                for key, val in g.attrs.iteritems():
                    if key.startswith("transform_"):
                        key = key.split("transform_")[1]
                        if key == "type":
                            val = getattr(sound_transforms, val)
                        elif key in ["children", "parents"]:
                            val = val.tolist()
                        metadata[key] = val
                return metadata
            else:
                raise KeyError("Requested data for id %s doesn't exist!" % id_)

    def get_data(self, id_, name="waveform"):

        id_ = unicode(id_)
        with h5py.File(self.filename, "r") as f:
            g = self._get_group(f, id_)
            if g:
                if name in g:
                    return g[name][:]
            else:
                raise KeyError("Requested data for id %s doesn't exist!" % id_)

    def list_data(self, id_):
        """
        Lists the datasets stored for the specified id
        :param id_: Unique sound id
        :return: a list of datasets
        """

        id_ = unicode(id_)
        with h5py.File(self.filename, "r") as f:
            g = self._get_group(f, id_)

            return g.keys()

    @writes
    def store_annotations(self, id_, ds=None, **kwargs):

        id_ = unicode(id_)
        with h5py.File(self.filename, "a") as f:
            g = self._get_group(f, id_)
            if ds is not None:
                if ds in g:
                    g = g[ds]
                else:
                    raise KeyError("Requested dataset %s not found. Nothing will be stored" % str(ds))
            for key, value in kwargs.iteritems():
                g.attrs[key] = value

        return True

    @writes
    def store_metadata(self, id_, **kwargs):

        id_ = unicode(id_)
        if "type" in kwargs:
            kwargs["type"] = kwargs["type"].__name__

        with h5py.File(self.filename, "a") as f:
            g = self._get_group(f, id_)
            for key, value in kwargs.iteritems():
                key = "transform_" + key
                if value is None:
                    value = 'None'
                g.attrs[key] = value

        return True

    @writes
    def store_data(self, id_, data, name="waveform", overwrite=True):

        id_ = unicode(id_)
        with h5py.File(self.filename, "a") as f:
            g = self._get_group(f, id_)

            if name not in g:
                g.create_dataset(name, data=data)
            else:
                # Will this work if data is not the same size as the current dataset?
                if overwrite:
                    g[name][:] = data

        return True

    def filter_ids(self, ids=None, num_matches=None, **kwargs):

        result_ids = list()
        with h5py.File(self.filename, "r") as f:
            if ids is None:
                ids = f.iterkeys()
            for name in ids:
                group = f[name]
                match = True
                for key, value in kwargs.iteritems():
                    if key in group.attrs:
                        if group.attrs[key] != value:
                            match = False
                            break
                    else:
                        match = False
                        break
                if match:
                    result_ids.append(name)

                if (num_matches is not None) and (len(result_ids) == num_matches):
                    break

        return result_ids

    def filter_by_func(self, ids=None, num_matches=None, **kwarg_funcs):

        result_ids = list()
        with h5py.File(self.filename, "r") as f:
            if ids is None:
                ids = f.iterkeys()
            for name in ids:
                group = f[name]
                match = True
                for key, func in kwarg_funcs.iteritems():
                    try:
                        if not func(group.attrs[key]):
                            match = False
                            break
                    except:
                        match = False
                        break
                if match:
                    result_ids.append(name)

                if (num_matches is not None) and (len(result_ids) == num_matches):
                    break

        return result_ids

    def list_ids(self):

        with h5py.File(self.filename, "r") as f:
            return f.keys()

    def list_annotation_values(self, key):

        values = list()
        with h5py.File(self.filename, "r") as f:
            for name, group in f.iteritems():
                if key in group.attrs:
                    value = group.attrs[key]
                    if value not in values:
                        values.append(value)

        return values