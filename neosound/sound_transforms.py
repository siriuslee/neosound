import re

from brian import second, Quantity, units, hertz
from brian.hears import dB, dB_type
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
            self.metadata.setdefault("parents", [self.original.id])
        else:
            self.metadata.setdefault("parents", [])

        self.manager.database.store_metadata(self.derived.id, **self.metadata)
        self.derived.transformation.update(self.metadata)

        self._update_children(self.metadata["parents"], self.derived.id)

        if self.save:
            self.manager.database.store_data(self.derived.id, asarray(self.derived))

        return self.derived

    def _update_children(self, parents, child):

        for parent in parents:
            metadata = self.manager.database.get_metadata(parent, "children")
            children = metadata.get("children", list())
            children.append(child)
            self.manager.database.store_metadata(parent, children=children)


class InitTransform(SoundTransform):

    def store(self):

        self.metadata.setdefault("parents", list())
        self.manager.database.store_metadata(self.derived.id, **self.metadata)
        self.derived.transformation.update(self.metadata)

        if self.save:
            self.manager.database.store_data(self.derived.id, asarray(self.derived))

        return self.derived

    @staticmethod
    def reconstruct(waveform, metadata, silence=False, manager=None):
        from neosound.sound import Sound

        if hasattr(waveform, "samplerate"):
            samplerate = waveform.samplerate
        else:
            samplerate = float(metadata["samplerate"]) * hertz

        if waveform is not None:
            sound = Sound(waveform, samplerate=samplerate, manager=manager)

        if silence:
            manager.logger.debug("Returning silence instead")
            return sound.to_silence()
        else:
            return sound


class LoadTransform(InitTransform):

    @staticmethod
    def reconstruct(waveform, metadata, silence=False, manager=None):
        from neosound.sound import Sound

        if hasattr(waveform, "samplerate"):
            samplerate = waveform.samplerate
        else:
            samplerate = float(metadata["samplerate"]) * hertz

        if waveform is not None:
            sound = Sound(waveform, samplerate=samplerate, manager=manager)
        else:
            sound = Sound(metadata["filename"], manager=manager)

        if silence:
            manager.logger.debug("Returning silence instead")
            return sound.to_silence()
        else:
            return sound


class CreateTransform(InitTransform):

    @staticmethod
    def reconstruct(waveform, metadata, silence=False, manager=None):
        from neosound.sound import Sound

        if hasattr(waveform, "samplerate"):
            samplerate = waveform.samplerate
        else:
            samplerate = float(metadata["samplerate"]) * hertz

        if waveform is not None:
            sound = Sound(waveform, samplerate=samplerate, manager=manager)
        else:
            create = getattr(Sound, metadata["sound"])
            for kw in ["sound", "type"]:
                metadata.pop(kw)

            for kw, val in metadata.iteritems():
                if not kw.endswith("_units"):
                    if "%s_units" % kw in metadata:
                        val_units = metadata.pop("%s_units" % kw)
                        val_units = eval(re.subn("[a-z]+", lambda m: "units.%s" % m.group(), val_units)[0])
                        metadata[kw] = val * val_units

            create(manager=manager, **metadata)

        if silence:
            manager.logger.debug("Returning silence instead")
            return sound.to_silence()
        else:
            manager.logger.debug("Found waveform: returning")
            return sound


class MonoTransform(SoundTransform):

    @staticmethod
    def reconstruct(waveforms, metadata, manager=None):
        from neosound.sound import Sound

        if hasattr(waveforms[0], "samplerate"):
            samplerate = waveforms[0].samplerate
        else:
            samplerate = float(metadata["samplerate"]) * hertz

        manager.logger.debug("Reconstructing mono transform")
        sound = Sound(waveforms[0], samplerate=samplerate, manager=manager)

        return sound.to_mono(read_only=True)


class FilterTransform(SoundTransform):

    # def store(self):
    #
    #     # self.derived = self.original.__class__(self.derived,
    #     #                                        samplerate=self.original.samplerate,
    #     #                                        manager=self.original.manager)
    #     return super(FilterTransform, self).store()

    @staticmethod
    def reconstruct(waveforms, metadata, manager=None):
        from neosound.sound import Sound

        if hasattr(waveforms[0], "samplerate"):
            samplerate = waveforms[0].samplerate
        else:
            samplerate = float(metadata["samplerate"]) * hertz

        manager.logger.debug("Reconstructing filter transform")
        sound = Sound(waveforms[0], samplerate=samplerate, manager=manager)
        frequency_range = [float(metadata["min_frequency"]) * hertz,
                           float(metadata["max_frequency"]) * hertz]

        return sound.filter(frequency_range,
                            filter_order=metadata["order"],
                            read_only=True)


class RampTransform(SoundTransform):

    @staticmethod
    def reconstruct(waveforms, metadata, manager=None):
        from neosound.sound import Sound

        if hasattr(waveforms[0], "samplerate"):
            samplerate = waveforms[0].samplerate
        else:
            samplerate = float(metadata["samplerate"]) * hertz

        manager.logger.debug("Reconstructing ramp transform")
        sound = Sound(waveforms[0], samplerate=samplerate, manager=manager)
        when = metadata["when"]
        duration = float(metadata["duration"]) * second

        return sound.ramp(when=when, duration=duration, read_only=True)


class ResampleTransform(SoundTransform):

    @staticmethod
    def reconstruct(waveforms, metadata, manager=None):
        from neosound.sound import Sound

        if hasattr(waveforms[0], "samplerate"):
            samplerate = waveforms[0].samplerate
        else:
            samplerate = float(metadata["samplerate"]) * hertz

        manager.logger.debug("Reconstructing resample transform")
        sound = Sound(waveforms[0], samplerate=samplerate, manager=manager)
        new_samplerate = float(metadata["new_samplerate"]) * hertz
        resample_type = metadata["resample_type"]

        return sound.resample(new_samplerate, resample_type=resample_type, read_only=True)


class PadTransform(SoundTransform):

    @staticmethod
    def reconstruct(waveforms, metadata, manager=None):
        from neosound.sound import Sound

        manager.logger.debug("Reconstructing pad transform")

        if hasattr(waveforms[0], "samplerate"):
            samplerate = waveforms[0].samplerate
        else:
            samplerate = float(metadata["samplerate"]) * hertz

        sound = Sound(waveforms[0], samplerate=samplerate, manager=manager)
        start = float(metadata["start_time"]) * second
        duration = float(metadata["duration"]) * second

        return sound.pad(duration, start=start, read_only=True)


class ClipTransform(SoundTransform):

    @staticmethod
    def reconstruct(waveforms, metadata, manager=None):
        from neosound.sound import Sound

        manager.logger.debug("Reconstructing clip transform")

        if hasattr(waveforms[0], "samplerate"):
            samplerate = waveforms[0].samplerate
        else:
            samplerate = float(metadata["samplerate"]) * hertz

        sound = Sound(waveforms[0], samplerate=samplerate, manager=manager)

        return sound.clip(metadata["max_value"], metadata["min_value"],
                          read_only=True)


class SliceTransform(SoundTransform):

    @staticmethod
    def reconstruct(waveforms, metadata, manager=None):
        from neosound.sound import Sound

        manager.logger.debug("Reconstructing slice transform")

        if hasattr(waveforms[0], "samplerate"):
            samplerate = waveforms[0].samplerate
        else:
            samplerate = float(metadata["samplerate"]) * hertz

        sound = Sound(waveforms[0], samplerate=samplerate, manager=manager)
        start = float(metadata["start_time"]) * second
        stop = float(metadata["stop_time"]) * second

        return sound.slice(start, stop, read_only=True)


class MultiplyTransform(SoundTransform):

    @staticmethod
    def reconstruct(waveforms, metadata, manager=None):
        from neosound.sound import Sound

        manager.logger.debug("Reconstructing multiply transform")

        if hasattr(waveforms[0], "samplerate"):
            samplerate = waveforms[0].samplerate
        else:
            samplerate = float(metadata["samplerate"]) * hertz

        sound = Sound(waveforms[0], samplerate=samplerate, manager=manager)
        level = float(metadata["level"]) * dB

        return sound.set_level(level, read_only=True)

class AddTransform(SoundTransform):

    @staticmethod
    def reconstruct(waveforms, metadata, manager=None):
        from neosound.sound import Sound

        manager.logger.debug("Reconstructing add transform")

        if hasattr(waveforms[0], "samplerate"):
            samplerate = waveforms[0].samplerate
        else:
            samplerate = float(metadata["samplerate"]) * hertz

        sound0 = Sound(waveforms[0], samplerate=samplerate, manager=manager)
        sound1 = Sound(waveforms[1], samplerate=samplerate, manager=manager)

        return sound0.combine(sound1, read_only=True)


class SetTransform(SoundTransform):

    # def store(self):
    #
    #     if not hasattr(self.original, "id"):
    #         self.original = self.derived.__class__(self.original, initialize=True, manager=self.manager)
    #
    #     tmp = self.derived.__class__(self.derived,
    #                                  manager=self.manager)
    #
    #     if not self.manager.read_only:
    #         self.manager.database.store_metadata(tmp.id, **self.metadata)
    #         self.derived.transformation.update(self.metadata)
    #         if self.original is not None:
    #             self.manager.database.store_metadata(tmp.id, parents=[self.derived.id, self.original.id])
    #             self._update_children(self.derived.id, tmp.id)
    #             self._update_children(self.original.id, tmp.id)
    #
    #         if self.save:
    #             self.manager.database.store_data(self.derived.id, asarray(self.derived))
    #
    #     self.derived.id = tmp.id

    @staticmethod
    def reconstruct(waveforms, metadata, manager=None):
        from neosound.sound import Sound

        manager.logger.debug("Reconstructing set transform")

        if hasattr(waveforms[0], "samplerate"):
            samplerate = waveforms[0].samplerate
        else:
            samplerate = float(metadata["samplerate"]) * hertz

        sound = Sound(waveforms[0], samplerate=samplerate, manager=manager)
        replacement = Sound(waveforms[1], samplerate=samplerate, manager=manager)
        start = float(metadata["start_time"]) * second
        stop = float(metadata["stop_time"]) * second
        return sound.replace(start,
                             stop,
                             replacement,
                             read_only=True)


class ComponentTransform(SoundTransform):

    @staticmethod
    def reconstruct(waveforms, metadata, manager):

        manager.logger.debug("Reconstructing component")

        return manager.reconstruct_individual(metadata["id"], metadata["root_id"])
