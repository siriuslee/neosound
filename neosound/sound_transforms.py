from brian import second, Quantity, units, hertz
from numpy import asarray


class SoundTransform(object):

    def __init__(self, manager, derived, metadata, original=None, save=False):

        self.manager = manager
        self.derived = derived
        self.original = original
        self.metadata = metadata
        self.save = save

    def store(self):

        if self.original is not None:
            self.derived = self.original.__class__(self.derived,
                                                   manager=self.original.manager)

        if not self.manager.reconstruct_flag:
            self.manager.database.store_metadata(self.derived.id, **self.metadata)

            if self.original is not None:
                self.manager.database.store_metadata(self.derived.id, parents=[self.original.id])
                self._update_children(self.original.id, self.derived.id)
            else:
                self.manager.database.store_metadata(self.derived.id, parents=[])

            if self.save:
                self.manager.database.store_data(self.derived.id, asarray(self.derived))

        return self.derived

    def _update_children(self, parent, child):

        metadata = self.manager.database.get_metadata(parent, "children")
        if metadata is None:
            children = list()
        else:
            children = metadata["children"]
        children.append(child)
        self.manager.database.store_metadata(parent, children=children)


class InitTransform(SoundTransform):

    @staticmethod
    def reconstruct(waveform, metadata, silence=False, manager=None):
        from neosound.sound import Sound

        if waveform is not None:
            sound = Sound(waveform, manager=manager)

        if silence:
            print("Returning silence instead")
            return sound.to_silence()
        else:
            return sound


class LoadTransform(SoundTransform):

    @staticmethod
    def reconstruct(waveform, metadata, silence=False, manager=None):
        from neosound.sound import Sound

        if waveform is not None:
            sound = Sound(waveform, manager=manager)
        else:
            sound = Sound(metadata["filename"], manager=manager)

        if silence:
            print("Returning silence instead")
            return sound.to_silence()
        else:
            return sound


class CreateTransform(SoundTransform):

    @staticmethod
    def reconstruct(waveform, metadata, silence=False, manager=None):
        from neosound.sound import Sound

        if waveform is not None:
            sound = Sound(waveform, manager=manager)
        else:
            create = getattr(Sound, metadata["sound"])
            metadata.pop("sound")
            create(manager=manager, **metadata)

        if silence:
            print("Returning silence instead")
            return sound.to_silence()
        else:
            print("Found waveform: returning")
            return sound


class MonoTransform(SoundTransform):

    @staticmethod
    def reconstruct(waveform, metadata, manager=None):
        from neosound.sound import Sound

        print("Reconstructing mono transform")
        sound = Sound(waveform, manager=manager)

        return sound.to_mono()


class FilterTransform(SoundTransform):

    def store(self):

        self.derived = self.original.__class__(self.derived,
                                               samplerate=self.original.samplerate,
                                               manager=self.original.manager)
        return super(FilterTransform, self).store()

    @staticmethod
    def reconstruct(waveform, metadata, manager=None):
        from neosound.sound import Sound

        print("Reconstructing filter transform")
        sound = Sound(waveform, manager=manager)

        return sound.filter([metadata["min_frequency"] * hertz,
                             metadata["max_frequency"] * hertz],
                            filter_order=metadata["order"])


class PadTransform(SoundTransform):

    @staticmethod
    def reconstruct(waveform, metadata, manager=None):
        from neosound.sound import Sound

        print("Reconstructing pad transform")
        sound = Sound(waveform, manager=manager)
        start = metadata["start_time"] * second
        duration = metadata["duration"] * second

        return sound.pad(duration, start=start)


class ClipTransform(SoundTransform):

    @staticmethod
    def reconstruct(waveform, metadata, manager=None):
        from neosound.sound import Sound

        print("Reconstructing clip transform")
        sound = Sound(waveform, manager=manager)

        return sound.clip(metadata["min_value"], metadata["max_value"])


class SliceTransform(SoundTransform):

    @staticmethod
    def reconstruct(waveform, metadata, manager=None):
        from neosound.sound import Sound

        print("Reconstructing slice transform")
        waveform = waveform[0]
        sound = Sound(waveform, manager=manager)

        return sound[metadata["start_time"] * second: metadata["end_time"] * second]


class MultiplyTransform(SoundTransform):

    @staticmethod
    def reconstruct(waveform, metadata, manager=None):
        from neosound.sound import Sound

        print("Reconstructing multiply transform")
        sound = Sound(waveform, manager=manager)
        coeff = metadata["coefficient"]

        return coeff * sound


class AddTransform(SoundTransform):

    def store(self):

        ids = [orig.id for orig in self.original]
        self.derived = self.original[0].__class__(self.derived,
                                                  manager=self.original[0].manager)
        if not self.manager.reconstruct_flag:
            self.manager.database.store_metadata(self.derived.id, **self.metadata)
            self.manager.database.store_metadata(self.derived.id, parents=ids)
            for orig_id in ids:
                self._update_children(orig_id, self.derived.id)

            if self.save:
                self.manager.database.store_data(self.derived.id, asarray(self.derived))

        return self.derived

    @staticmethod
    def reconstruct(waveforms, metadata, manager=None):
        from neosound.sound import Sound

        print("Reconstructing add transform")
        sound0 = Sound(waveforms[0], manager=manager)
        sound1 = Sound(waveforms[1], manager=manager)

        return sound0 + sound1


class SetTransform(SoundTransform):

    def store(self):

        if not hasattr(self.original, "id"):
            self.original = self.derived.__class__(self.original, initialize=True, manager=self.derived.manager)

        tmp = self.derived.__class__(self.derived,
                                     manager=self.derived.manager)

        if not self.manager.reconstruct_flag:
            self.manager.database.store_metadata(tmp.id, **self.metadata)
            if self.original is not None:
                self.manager.database.store_metadata(tmp.id, parents=[self.derived.id, self.original.id])
                self._update_children(self.derived.id, tmp.id)
                self._update_children(self.original.id, tmp.id)

            if self.save:
                self.manager.database.store_data(self.derived.id, asarray(self.derived))

        self.derived.id = tmp.id

    @staticmethod
    def reconstruct(waveforms, metadata, manager=None):
        from neosound.sound import Sound

        print("Reconstructing set transform")
        sound = Sound(waveforms[0], manager=manager)
        replacement = Sound(waveforms[1], manager=manager)
        sound[metadata["start_time"] * second: metadata["end_time"] * second] = replacement

        return sound

