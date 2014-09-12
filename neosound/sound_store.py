import copy
import h5py
from neosound import sound_transforms


class SoundStore(object):

    def __init__(self):

        self.data = dict()

    def store_annotations(self, id_, **kwargs):

        self.data.setdefault(id_, dict()).update(kwargs)

    def get_annotations(self, id_):

        try:
            annotations = dict([(key, val) for key, val in self.data[id_].iteritems() if not key.startswith(
                "transform_")])
            return annotations
        except KeyError:
            return dict()

    def store_metadata(self, id_, **kwargs):

        if "type" in kwargs:
            kwargs["type"] = kwargs["type"].__name__
        metadata = dict([("transform_" + key, value) for key, value in kwargs.iteritems()])
        self.data.setdefault(id_, dict()).update(metadata)

    def store_data(self, id_, data):

        self.data.setdefault(id_, dict())["waveform"] = data

    def get_metadata(self, id_, *args):

        try:
            if len(args):
                metadata = dict([(ss, self.data[id_]["transform_" + ss]) for ss in args])
            else:
                metadata = dict([(key.split("transform_")[1], val) for key, val in self.data[id_].iteritems() if
                                 key.startswith("transform_")])
            if "type" in metadata:
                metadata["type"] = getattr(sound_transforms, metadata["type"])

            return metadata
        except KeyError:
            return None

    def get_data(self, id_):

        try:
            return self.data[id_]["waveform"]
        except KeyError:
            return None

    def list_ids(self):

        return self.data.keys()


class HDF5Store(object):
    '''Stores data in an hdf5 file.
    TODO: We probably want all calls to write data to use a "with statement"
    '''

    def __init__(self, filename, *args, **kwargs):

        self.filename = filename
        self.f = h5py.File(self.filename, "a")

    def _get_group(self, group_name):

        try:
            g = self.f[group_name]
        except KeyError:
            g = self.f.create_group(group_name)
        return g

    def store_annotations(self, id_, **kwargs):
        id_ = str(id_)

        g = self._get_group(id_)
        for key, value in kwargs.iteritems():
            g.attrs[key] = value

    def get_annotations(self, id_):
        id_ = str(id_)

        try:
            annotations = dict([(key, value) for key, value in self.f[id_].attrs.iteritems() if not key.startswith(
                "transform_")])
            return annotations
        except KeyError:
            return dict()

    def store_metadata(self, id_, **kwargs):
        id_ = str(id_)

        if "type" in kwargs:
            kwargs["type"] = kwargs["type"].__name__

        g = self._get_group(id_)
        for key, value in kwargs.iteritems():
            key = "transform_" + key
            if value is None:
                value = 'None'
            g.attrs[key] = value

    def store_data(self, id_, data):
        id_ = str(id_)

        try:
            g = self.f[id_]
        except KeyError:
            g = self.f.create_group(id_)

        g.create_dataset("waveform", data=data)

    def get_metadata(self, id_, *args):
        id_ = str(id_)

        try:
            if len(args):
                metadata = dict([(ss, self.f[id_].attrs["transform_" + ss]) for ss in args])
            else:
                metadata = dict([(key.split("transform_")[1], val) for key, val in self.f[
                    id_].attrs.iteritems() if key.startswith("transform_")])
            if "type" in metadata:
                metadata["type"] = getattr(sound_transforms, metadata["type"])
            for ss in ["children", "parents"]:
                if ss in metadata:
                    metadata[ss] = metadata[ss].tolist()

            return metadata
        except KeyError:
            return None

    def get_data(self, id_):
        id_ = str(id_)
        try:
            return self.f[id_]["waveform"][:]
        except KeyError:
            return None

    def filter_ids(self, **kwargs):

        result_ids = list()
        for name, group in self.f.iteritems():
            match = True
            for key, value in kwargs.iteritems():
                try:
                    if group.attrs[key] != value:
                        match = False
                        break
                except:
                    match = False
                    break
            if match:
                result_ids.append(int(name))

        return result_ids

    def filter_by_func(self, **kwarg_funcs):

        result_ids = list()
        for name, group in self.f.iteritems():
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
                result_ids.append(int(name))

        return result_ids

    def list_ids(self):

        return [int(kk) for kk in self.f.keys()]

    def list_roots(self):

        return self.filter_by_func(transform_parents=lambda x: len(x) == 0)


class MatlabStore(SoundStore):

    def __init__(self, filename, *args, **kwargs):

        super(MatlabStore, self).__init__(filename, *args, **kwargs)

    def store_metadata(self, **kwargs):

        pass

    def store_data(self, **kwargs):

        pass

    def get_metadata(self, **kwargs):

        pass

    def get_data(self, **kwargs):

        pass

    def list_ids(self):

        pass
