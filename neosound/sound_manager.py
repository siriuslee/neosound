import random
from brian import second, Quantity, units

class SoundManager(object):

    def __init__(self, sound_store=None):

        self.store = sound_store
        self.ids = None
        # self.list_ids()

    def get_id(self):

        return random.randint(0, 1e6)

    def new_id(self, sound_object):

        sid = self.ids[-1] + 1
        sound_object.id = sid
        self.ids.append(sid)

    def list_ids(self):

        ids = self.store.get_ids()
        ids.sort()
        self.ids = ids


inherit_attributes = ["samplerate",
                      "start_time",
                      "end_time",
                      ]


class SoundTransform(object):

    def __init__(self, derived, original=None):

        self.derived = derived
        self.original = original

    def transform(self, keep_annotations=[]):

        if self.original is not None:
            self._merge(keep_annotations)
        return self.derived

    def _merge(self, keep_annotations):
        '''
        Merge all the properties we want to keep from a previous Sound object.
        :param other: A previous Sound object used to initialize this one.
        '''

        # Bring over all annotations from other...
        for ka in keep_annotations:
            try:
                self.original.annotations.pop(ka)
            except KeyError:
                pass

        self.derived.annotate(**self.original.annotations)

        # and any member variables that we want to keep.
        for key in inherit_attributes:
            if hasattr(self.original, key):
                val = getattr(self.original, key)
                setattr(self.derived, key, val)

class ReinitializeTransform(SoundTransform):

    def __init__(self, *args, **kwargs):

        super(ReinitializeTransform, self).__init__(*args, **kwargs)
        self.derived = self.original.__class__(self.derived, merge_metadata=self.original)

    def transform(self, **kwargs):

        super(ReinitializeTransform, self).transform(**kwargs)

class AddTransform(SoundTransform):

    def __init__(self, *args, **kwargs):

        super(AddTransform, self).__init__(*args, **kwargs)

    def transform(self):

        pass

class LevelTransform(SoundTransform):

    def __init__(self, *args, **kwargs):

        super(LevelTransform, self).__init__(*args, **kwargs)

    def transform(self):

        pass

class ItemTransform(SoundTransform):

    def __init__(self, *args, **kwargs):

        super(ItemTransform, self).__init__(*args, **kwargs)

    def _keydata(self, key):

        if isinstance(key, (int, float)):
            start = key / self.derived.samplerate
            stop = None
        elif isinstance(key, Quantity):
            start = key
            stop = None
        elif isinstance(key, (slice, tuple)):
            if isinstance(key, tuple):
                key = key[0]

            if key.start is None:
                start = 0 * second
            elif units.have_same_dimensions(key.start, second):
                start = key.start
            else:
                start = key.start / self.derived.samplerate

            if key.stop is None:
                stop = self.derived.duration
            elif units.have_same_dimensions(key.stop, second):
                stop = key.stop
            else:
                stop = key.stop / self.derived.samplerate
        else:
            raise TypeError("__getitem__ key is of an unexpected type: %s." % str(type(key)))

        return start, stop


class SliceTransform(ReinitializeTransform, ItemTransform):

    def __init__(self, *args, **kwargs):

        super(SliceTransform, self).__init__(*args, **kwargs)

    def transform(self, key=None, start=None, stop=None, **kwargs):

        if key is not None:
            start, stop = self._keydata(key)

        self._clip_times(start, stop)
        # super(SliceTransform, self).transform(keep_annotations=["original_start_time", "original_end_time"])

        return self.derived

    def _clip_times(self, start=0*second, stop=None):

        if stop is None:
            stop = start

        # Check that the attributes exist:
        # if "original_start_time" not in self.derived.annotations:
        #     self.derived.annotate(original_start_time=0*second)

        # Get the difference between slice start time and start time for current waveform
        delta = (start - self.derived.start_time)
        # If delta > 0, we are indexing into this components waveform
        self.derived.annotations["original_start_time"] += max(delta, 0 * second)
        # If we are indexing into this component, the new start time is 0, otherwise it's -delta
        self.derived.start_time = max(-delta, 0 * second)

        # Get the difference between slice stop time and the stop time for the current waveform
        delta = (stop - self.derived.end_time)
        # If delta < 0, then we are indexing into this component's waveform
        self.derived.annotations["original_end_time"] -= max(-delta, 0 * second)
        # If delta is < 0, then the component indexes to the end of the waveform
        self.derived.end_time = min(self.derived.end_time - start, self.derived.duration)


class ShiftTransform(ItemTransform):

    def __init__(self, *args, **kwargs):

        super(ShiftTransform, self).__init__(*args, **kwargs)

    def transform(self, key=None, start=None, stop=None, **kwargs):

        if key is not None:
            start, stop = self._keydata(key)

        self.derived.start_time += start
        self.derived.end_time += start

        super(ShiftTransform, self).transform(**kwargs)

        return self.derived

class RampTransform(SoundTransform):

    def __init__(self, *args, **kwargs):

        super(RampTransform, self).__init__(*args, **kwargs)

    def transform(self):

        pass

