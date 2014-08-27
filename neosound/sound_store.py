


class SoundStore(object):

    def __init__(self, filename, *args, **kwargs):

        self.filename = filename

    def save(self):

        pass

    def load(self):

        pass

    def list_ids(self):

        pass

class HDF5Store(SoundStore):

    def __init__(self, filename, *args, **kwargs):

        super(HDF5Store, self).__init__(filename, *args, **kwargs)

    def save(self):

        pass

    def load(self):

        pass

    def list_ids(self):

        pass

class MatlabStore(SoundStore):

    def __init__(self, filename, *args, **kwargs):

        super(MatlabStore, self).__init__(filename, *args, **kwargs)

    def save(self):

        pass

    def load(self):

        pass

    def list_ids(self):

        pass

