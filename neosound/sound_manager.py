import logging
import os
import copy

import numpy as np

from neosound.sound_store import *
from neosound.sound_transforms import *

this_dir, this_filename = os.path.split(__file__)
data_dir = os.path.join(this_dir, "..", "data")

# TODO: need to fix the circular import problem...

class SoundManager(object):
    _default_database = DictStore()
    logging.basicConfig()
    logger = logging.getLogger()
    logger.setLevel(logging.WARN)

    def __init__(self, database=None, filename=None, read_only=False, **db_args):
        """
        Initialize a SoundManager object. If no database is provided, the default one will be chosen. If one has
        been recently used (i.e. since the class was defined), then that one will be chosen. Otherwise,
        a non-persistent dictionary-based storage will be used.

        :param database: A subclass of SoundStore responsible for persisting sounds to a file.
        :param filename: The name of the persistent sound store file.
        :param read_only: prevents writing to the database if True
        :param db_args: A dictionary of arguments that will be passed to the constructor of database.
        """

        if database is None:
            self.database = self._default_database
        else:
            self.database = database(filename, read_only=read_only, **db_args)
            self._default_database = self.database

    def get_id(self):
        """
        Get a unique id from the database.
        """

        return self.database.get_id()

    def import_ids(self, manager, ids, recursive=False, reconstruct_necessary=True, **kwargs):
        """
        Imports ids from manager and adds them to the current database.
        :param manager: Another sound manager that stored ids
        :param ids: list of ids to import from the manager
        :param recursive: if True, import the parents of the ids too. (False)
        :param reconstruct_necessary: if True, reconstruct all sounds whose parents aren't imported. (True)
        :param kwargs: all other kwargs are added as annotations to each imported id
        :returns a list of ids in the new manager corresponding to the input ids
        """

        processed_ids = dict()
        for id_ in ids:
            if id_ not in processed_ids: # Don't import the same ID twice
                new_id = self.get_id()
                self.logger.debug("Importing id %s with new id %s" % (id_, new_id))

                # import annotations
                annotations = manager.database.get_annotations(id_)
                self.database.store_annotations(new_id, **annotations)
                self.database.store_annotations(new_id, **kwargs)

                # import transformation metadata
                metadata = manager.database.get_metadata(id_)
                self.database.store_metadata(new_id, **metadata)

                # import data
                data = manager.database.get_data(id_)
                if data is not None:
                    self.database.store_data(new_id, data)

                processed_ids[id_] = new_id

                if recursive:
                    if "parents" in metadata:
                        ids.extend(metadata["parents"])

        # Fix parents and children
        for id_, new_id in processed_ids.iteritems():
            self.logger.debug("Converting parents and children attributes for id %s" % new_id)
            metadata = self.database.get_metadata(new_id)
            if "parents" in metadata:
                parents = metadata.pop("parents")
                try:
                    metadata["parents"] = list()
                    for pid in parents:
                        metadata["parents"].append(processed_ids[pid])
                except KeyError: #
                    data = self.database.get_data(new_id)
                    if (data is None) and reconstruct_necessary:
                        self.logger.debug("Parents of %s not in database. Attempting to reconstruct and store data" % new_id)
                        data = np.asarray(manager.reconstruct(id_))
                        self.database.store_data(new_id, data)

            if "children" in metadata:
                children = metadata.pop("children")
                metadata["children"] = list()
                for cid in children:
                    if cid in processed_ids:
                        metadata["children"].append(processed_ids[cid])

            self.database.store_metadata(new_id, **metadata)

        return [processed_ids[id_] for id_ in ids]

    def store(self, derived, metadata, original=None):
        """
        Attempt to store the new sound object in the database.
        :param derived: The new sound object
        :param metadata: a dictionary of transformation metadata
        :param original: the parent sound object that was modified to produce derived
        :return: True if sound was stored, else False
        """

        if "type" in metadata:
            transform = metadata["type"](self, derived, metadata, original)
        else:
            raise KeyError("Error trying to store sound transformation metadata: metadata does not contain a key 'type'")

        return transform.store()

    def get_transformation_metadata(self, id_):

        return self.database.get_metadata(id_)

    # I think these recursive methods can be done better, but that's low priority
    def get_roots(self, id_):

        roots = list()
        metadata = self.database.get_metadata(id_)
        if ("parents" in metadata) and len(metadata["parents"]):
            for pid in metadata["parents"]:
                roots.extend(self.get_roots(pid))
        else:
            roots.append(id_)

        return roots

    def reconstruct_individual(self, id_, root_id):
        from neosound.sound import Sound

        def get_waveform_ind(id_):
            self.logger.debug("Attempting to get waveform for id %s" % id_)

            metadata = self.database.get_metadata(id_)
            transform = metadata["type"]
            if ("parents" in metadata) and len(metadata["parents"]):
                pids = metadata["parents"]
                self.logger.debug("Attempting to reconstruct from %s parents" % len(pids))
                return transform.reconstruct([get_waveform_ind(pid) for pid in pids],
                                             metadata,
                                             manager=self)
            else:
                self.logger.debug("parents not found in database for id %s. Attempting to reconstruct!" % id_)
                # If this root id is not in root_ids, we want to replace the waveform with silence
                silence = id_ != root_id
                waveform = self.database.get_data(id_)
                return transform.reconstruct(waveform,
                                             metadata,
                                             silence,
                                             manager=self)

        roots = self.get_roots(id_)
        if root_id not in roots:
            self.logger.debug("Requested root_id not roots for id %s" % id_)
            return None

        component_id = self.database.filter_ids(transform_id=id_,
                                                transform_root_id=root_id)
        if len(component_id):

            component_id = component_id[0]
            data = self.database.get_data(component_id)
            if data is not None:
                samplerate = self.database.get_annotations(component_id)["samplerate"]
                sound = Sound(data, samplerate=samplerate*hertz, manager=self)
                sound.id = component_id
                sound.annotations.update(self.database.get_annotations(component_id))

                return sound
            else:
                store = True
                metadata = dict(type=ComponentTransform,
                                id=id_,
                                root_id=root_id,
                                parents=[id_, root_id])

        else:
            store = True
            metadata = dict(type=ComponentTransform,
                            id=id_,
                            root_id=root_id,
                            parents=[id_, root_id])

        sound = get_waveform_ind(id_)
        if store:
            self.store(sound, metadata)

        return sound

    def reconstruct(self, id_):
        from neosound.sound import Sound

        def get_waveform(id_):

            self.logger.debug("Attempting to get waveform for id %s" % id_)
            data = self.database.get_data(id_)
            if data is not None:
                samplerate = self.database.get_annotations(id_)["samplerate"]
                return Sound(data, samplerate=samplerate * hertz, manager=self)
            else:
                self.logger.debug("Attempting to get waveform from parents instead")
                metadata = self.database.get_metadata(id_)
                transform = metadata["type"]

                if ("parents" in metadata) and len(metadata["parents"]):
                    pids = metadata["parents"]
                    self.logger.debug("Attempting to reconstruct from %s parents" % len(pids))
                    return transform.reconstruct([get_waveform(pid) for pid in pids],
                                                 metadata,
                                                 manager=self)
                else:
                    self.logger.debug("parents not found in database for id %s. Attempting to reconstruct!" % id_)
                    waveform = self.database.get_data(id_)
                    return transform.reconstruct(waveform,
                                                 metadata,
                                                 manager=self)

        sound = get_waveform(id_)
        sound.id = id_
        sound.annotations.update(self.database.get_annotations(id_))

        return sound



