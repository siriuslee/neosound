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

    def __init__(self, database=None, filename=None, db_args=None, read_only=False):
        """ Initialize a SoundManager object. If no database is provided, the default one will be chosen. If one has been recently used (ie since the class was defined), then that one will be chosen. Otherwise, no data will be stored.

        :param database: A subclass of SoundStore responsible for persisting sounds to a file.
        :param filename: The name of the sound file.
        :param db_args: A dictionary of arguments that will be passed to the constructor of database.
        :param read_only: prevents writing to the database if True
        """

        if db_args is None:
            db_args = dict()

        if database is None:
            self.database = self._default_database
        else:
            self.database = database(filename, **db_args)
            self._default_database = self.database

        self.read_only = read_only

    def get_id(self):

        return self.database.get_id()

    def store(self, derived, metadata, original=None, save=False):

        if self.read_only:
            return derived

        try:
            transform = metadata["type"](self, derived, metadata, original, save)
        except KeyError as e:
            raise KeyError("Error trying to store sound transformation metadata: %s" % e)

        derived = transform.store()
        return derived

    # I think these recursive methods can be done better, but that's low priority
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
                # Should probably check if this is not there
                samplerate = self.database.get_annotations(component_id)["samplerate"]
                sound = Sound(data, samplerate=samplerate * hertz, manager=self)
                sound.id = component_id
                sound.annotations.update(self.database.get_annotations(component_id))
                sound.transformation.update(self.database.get_metadata(component_id))

                return sound
        else:
            store = True
            metadata = dict(type=ComponentTransform,
                            id=id_,
                            root_id=root_id)

        # This can be done better. Probably shouldn't use a bare except
        previous_read_only = self.read_only
        try:
            self.read_only = True
            sound = get_waveform_ind(id_)
        except:
            raise
        finally:
            self.read_only = previous_read_only

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
                # Should probably do something if samplerate is not there
                samplerate = self.database.get_annotations(id_)["samplerate"]
                return Sound(data, samplerate=samplerate * hertz, manager=self)
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



