import logging
import os

import numpy as np

from neosound.sound_store import *
from neosound.sound_transforms import *

this_dir, this_filename = os.path.split(__file__)
data_dir = os.path.join(this_dir, "..", "data")

class SoundManager(object):
    _default_database = SoundStore()
    logger = logging.Logger(os.path.join(data_dir, "sound_log"), level=30)

    def __init__(self, database=None, filename=None):

        if database is None:
            self.database = self._default_database
        else:
            # Create temporary database filename
            # if filename is None:
            self.database = database(filename)
            self._default_database = self.database

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

    def reconstruct_individual(self, id_, root_id):
        from neosound.sound import Sound

        def get_waveform_ind(id_):
            self.logger.debug("Attempting to get waveform for id %d" % id_)
            metadata = self.database.get_metadata(id_)
            if len(metadata) == 0:
                raise KeyError("%d not in database!" % id_)
            transform = metadata["type"].reconstruct

            try:
                self.logger.debug("Attempting to get waveform from parents instead")
                pids = metadata["parents"]
                if len(pids):
                    self.logger.debug("Attempting to reconstruct from %d parents" % len(pids))
                    return transform([get_waveform_ind(pid) for pid in pids], metadata, manager=self)
                else:
                    raise KeyError
            except KeyError:
                # ipdb.set_trace()
                self.logger.debug("parents not found in database for id %d. Attempting to reconstruct!" % id_)
                # If this root id is not in root_ids, we want to replace the waveform with silence
                silence = id_ != root_id
                waveform = self.database.get_data(id_)
                return transform(waveform, metadata, silence, manager=self)

        roots = self.get_roots(id_)
        if root_id not in roots:
            self.logger.debug("Requested root_id not roots for id %d" % id_)
            return None

        component_id = self.database.filter_ids(transform_id=id_,
                                                transform_root_id=root_id)
        if len(component_id):
            store = False
            component_id = component_id[0]
            data = self.database.get_data(component_id)
            if data is not None:
                sound = Sound(data, manager=self)
                sound.id = component_id
                sound.annotations.update(self.database.get_annotations(component_id))
                sound.transformation.update(self.database.get_metadata(component_id))

                return sound
        else:
            store = True
            metadata = dict(type=ComponentTransform,
                            id=id_,
                            root_id=root_id)

        self.reconstruct_flag = True
        sound = get_waveform_ind(id_)
        self.reconstruct_flag = False
        if store:
            sound = self.store(sound, metadata)

        return sound

    def reconstruct(self, id_):
        from neosound.sound import Sound

        self.reconstruct_flag = True

        def get_waveform(id_):

            self.logger.debug("Attempting to get waveform for id %d" % id_)
            metadata = self.database.get_metadata(id_)
            if len(metadata) == 0:
                raise KeyError("%d not in database!" % id_)
            transform = metadata["type"].reconstruct
            data = self.database.get_data(id_)
            if data is not None:
                return Sound(data, manager=self)
            else:
                try:
                    self.logger.debug("Attempting to get waveform from parents instead")
                    pids = metadata["parents"]
                    if len(pids):
                        self.logger.debug("Attempting to reconstruct from %d parents" % len(pids))
                        return transform([get_waveform(pid) for pid in pids], metadata, manager=self)
                    else:
                        raise KeyError
                except KeyError:
                    self.logger.debug("parents not found in database for id %d. Attempting to reconstruct!" % id_)
                    waveform = self.database.get_data(id_)
                    return transform(waveform, metadata, manager=self)

        sound = get_waveform(id_)
        sound.id = id_
        sound.annotations.update(self.database.get_annotations(id_))
        sound.transformation.update(self.database.get_metadata(id_))
        self.reconstruct_flag = False
        return sound



