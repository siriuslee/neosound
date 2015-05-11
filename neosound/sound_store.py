import copy
import os
import uuid

import h5py
from neosound import sound_transforms


class SoundStore(object):

    def __init__(self):

        self.data = dict()

    def get_id(self):

        return str(uuid.uuid4())

    def get_annotations(self, id_):

        annotations = dict((key, value) for key, value in self.data[id_].iteritems() if not key.startswith("transform_"))
        return annotations

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
            return dict()

    def get_data(self, id_):

        try:
            return self.data[id_]["waveform"]
        except KeyError:
            return None

    def store_annotations(self, id_, **kwargs):

        self.data.setdefault(id_, dict()).update(kwargs)



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

    def filter_ids(self, num_matches=None, **kwargs):

        result_ids = list()
        for name, annotations in self.data.iteritems():
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

    def filter_by_func(self, num_matches=None, **kwarg_funcs):

        result_ids = list()
        for name, annotations in self.data.iteritems():
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



class HDF5Store(object):
    '''Stores data in an hdf5 file.
    TODO: We probably want all calls to write data to use a "with statement"
    '''

    def __init__(self, filename, *args, **kwargs):

        self.filename = filename
        self.read_only = 'read_only' in kwargs and kwargs['read_only']
        if not os.path.exists(filename):
            with h5py.File(self.filename, "a") as f:
                pass

    def _get_group(self, f, group_name):

        # if group_name in self._ids:
        if group_name in f:
            g = f[group_name]
        else:
            g = f.create_group(group_name)
        return g

    def get_id(self):

        return str(uuid.uuid4())
    
    def get_annotations(self, id_):
        id_ = unicode(id_)

        with h5py.File(self.filename, "r") as f:
            try:
                annotations = dict([(key, value) for key, value in f[id_].attrs.iteritems() if not key.startswith("transform_")])
                return annotations
            except KeyError:
                return dict()

    def get_metadata(self, id_, *args):
        id_ = unicode(id_)

        with h5py.File(self.filename, "r") as f:
            # if id_ in self._ids:
            if id_ in f:
                g = f[id_]
                if len(args):
                    metadata = dict([(ss, g.attrs["transform_" + ss]) for ss in args if "transform_" + ss in
                                     g.attrs])
                else:
                    metadata = dict([(key.split("transform_")[1], val) for key, val in g.attrs.iteritems() if
                                     key.startswith("transform_")])
                if "type" in metadata:
                    metadata["type"] = getattr(sound_transforms, metadata["type"])
                for ss in ["children", "parents"]:
                    if ss in metadata:
                        metadata[ss] = metadata[ss].tolist()

                return metadata
            else:
                return dict()

    def get_data(self, id_):
        id_ = unicode(id_)

        with h5py.File(self.filename, "r") as f:
            try:
                return f[id_]["waveform"][:]
            except KeyError:
                return None

    def store_annotations(self, id_, **kwargs):
        if self.read_only:
            return

        id_ = unicode(id_)

        with h5py.File(self.filename, "a") as f:
            g = self._get_group(f, id_)
            for key, value in kwargs.iteritems():
                g.attrs[key] = value

    def store_metadata(self, id_, **kwargs):
        if self.read_only:
            return

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

    def store_data(self, id_, data, overwrite=True):
        if self.read_only:
            return

        id_ = unicode(id_)

        with h5py.File(self.filename, "a") as f:
            g = self._get_group(f, id_)

            if "waveform" not in g:
                g.create_dataset("waveform", data=data)
            else:
                if overwrite:
                    g["waveform"][:] = data

    def filter_ids(self, num_matches=None, **kwargs):

        result_ids = list()
        with h5py.File(self.filename, "r") as f:
            for name, group in f.iteritems():
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

    def filter_by_func(self, **kwarg_funcs):

        result_ids = list()
        with h5py.File(self.filename, "r") as f:
            for name, group in f.iteritems():
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


class PandasStore(HDF5Store):
    '''Stores data in an hdf5 file.
    All waveform data is stored in a group "waveforms" underneath the root of the file.
    All metadata and annotations are stored in a pytables table object.
    Metadata correspond to the parameters of the transforms that were used to generate that sound.
    Annotations are any additional information stored with the sound object.
    '''

    def __init__(self, filename, *args, **kwargs):

        super(PandasStore, self).__init__(filename, *args, **kwargs)
        # Create a DataFrame in the root of the hdf5 file
        with h5py.File(self.filename, "r") as f:
            if "metadata" in f:
                self._metadata = pd.fr
            else:
                self._metadata = pd.DataFrame()
                self._metadata.to_hdf(f, "metadata", format="table", append=True)

    def store_annotations(self, id_, **kwargs):
        if self.read_only:
            return

        id_ = unicode(id_)

        with h5py.File(self.filename, "a") as f:
            g = self._get_group(f, id_)
            for key, value in kwargs.iteritems():
                g.attrs[key] = value

    def get_annotations(self, id_):
        id_ = unicode(id_)

        with h5py.File(self.filename, "r") as f:
            try:
                annotations = dict([(key, value) for key, value in f[id_].attrs.iteritems() if not key.startswith("transform_")])
                return annotations
            except KeyError:
                return dict()

    def store_metadata(self, id_, **kwargs):
        if self.read_only:
            return

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

    def get_metadata(self, id_, *args):
        id_ = unicode(id_)

        with h5py.File(self.filename, "r") as f:
            # if id_ in self._ids:
            if id_ in f:
                g = f[id_]
                if len(args):
                    metadata = dict([(ss, g.attrs["transform_" + ss]) for ss in args if "transform_" + ss in
                                     g.attrs])
                else:
                    metadata = dict([(key.split("transform_")[1], val) for key, val in g.attrs.iteritems() if
                                     key.startswith("transform_")])
                if "type" in metadata:
                    metadata["type"] = getattr(sound_transforms, metadata["type"])
                for ss in ["children", "parents"]:
                    if ss in metadata:
                        metadata[ss] = metadata[ss].tolist()

                return metadata
            else:
                return dict()

    def filter_ids(self, num_matches=None, **kwargs):

        result_ids = list()
        with h5py.File(self.filename, "r") as f:
            for name, group in f.iteritems():
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
                    result_ids.append(int(name))

                if (num_matches is not None) and (len(result_ids) == num_matches):
                    break

        return result_ids

    def filter_by_func(self, **kwarg_funcs):

        result_ids = list()
        with h5py.File(self.filename, "r") as f:
            for name, group in f.iteritems():
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

        with h5py.File(self.filename, "r") as f:
            return [int(kk) for kk in f.keys()]

    def list_annotation_values(self, key):

        values = list()
        with h5py.File(self.filename, "r") as f:
            for name, group in f.iteritems():
                if key in group.attrs:
                    value = group.attrs[key]
                    if value not in values:
                        values.append(value)

        return values

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
