import numpy as np
from neosound.sound_store import *
from neosound.sound_transforms import *


class SoundManager(object):

    def __init__(self, database=None, filename=None):

        if database is None:
            self.database = SoundStore()
        else:
            # Create temporary database filename
            # if filename is None:
            self.database = database(filename)

        self.ids = self.database.list_ids()
        self.reconstruct_flag = False

    def get_id(self):

        self.ids = self.database.list_ids()
        max_id = np.max(self.ids) if len(self.ids) else 0

        return max_id + 1

    def store(self, derived, metadata, original=None, save=False):

        try:
            transform = metadata["type"](self, derived, metadata, original, save)
        except KeyError as e:
            raise KeyError("Error trying to store sound transformation metadata: %s" % e)

        derived = transform.store()
        return derived

    def get_roots(self, id_):

        def get_parents(id_):
            metadata = self.database.get_metadata(id_, "parents")
            if (metadata is not None) and (len(metadata["parents"])):
                for pid in metadata["parents"]:
                    get_parents(pid)
            else:
                roots.append(id_)

        roots = list()
        get_parents(id_)
        return roots

    def reconstruct_individual(self, id_, root_ids):

        def get_waveform_ind(id_):

            print("Attempting to get waveform for id %d" % id_)
            metadata = self.database.get_metadata(id_)
            if metadata is None:
                raise KeyError("%d not in database!" % id_)
            transform = metadata["type"].reconstruct

            try:
                print("Attempting to get waveform from parents instead")
                pids = metadata["parents"]
                if len(pids):
                    print("Attempting to reconstruct from %d parents" % len(pids))
                    return transform([get_waveform_ind(pid) for pid in pids], metadata, manager=self)
                else:
                    raise KeyError
            except KeyError:
                # ipdb.set_trace()
                print("parents not found in database for id %d. Attempting to reconstruct!" % id_)
                # If this root id is not in root_ids, we want to replace the waveform with silence
                silence = id_ not in root_ids
                waveform = self.database.get_data(id_)
                return transform(waveform, metadata, silence, manager=self)

        if not isinstance(root_ids, (list, tuple)):
            root_ids = [root_ids]

        roots = self.get_roots(id_)
        root_ids = [root_id for root_id in root_ids if root_id in roots]
        if len(root_ids) == 0:
            print("Requested root_ids not roots for id %d" % id_)
            return None

        self.reconstruct_flag = True
        sound = get_waveform_ind(id_)
        sound.id = id_
        self.reconstruct_flag = False

        return sound

    def reconstruct(self, id_):
        from neosound.sound import Sound

        self.reconstruct_flag = True

        def get_waveform(id_):

            print("Attempting to get waveform for id %d" % id_)
            metadata = self.database.get_metadata(id_)
            if metadata is None:
                raise KeyError("%d not in database!" % id_)
            transform = metadata["type"].reconstruct
            data = self.database.get_data(id_)
            if data is not None:
                return Sound(data, manager=self)
            else:
                try:
                    print("Attempting to get waveform from parents instead")
                    pids = metadata["parents"]
                    if len(pids):
                        print("Attempting to reconstruct from %d parents" % len(pids))
                        return transform([get_waveform(pid) for pid in pids], metadata, manager=self)
                    else:
                        raise KeyError
                except KeyError:
                    print("parents not found in database for id %d. Attempting to reconstruct!" % id_)
                    waveform = self.database.get_data(id_)
                    return transform(waveform, metadata, manager=self)

        sound = get_waveform(id_)
        sound.id = id_
        sound.annotations.update(self.database.get_annotations(id_))
        sound.transformation.update(self.database.get_metadata(id_))
        self.reconstruct_flag = False
        return sound



