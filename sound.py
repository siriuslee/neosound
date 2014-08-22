from __future__ import division, print_function
import re
import os
from brian import second, hertz
from brian.hears import dB
from brian.hears import Sound as BHSound
from lasp.signal import lowpass_filter, bandpass_filter, highpass_filter
try:
    from neo.core.baseneo import _check_annotations
except ImportError:
    from pecking.annotations import _check_annotations


class Sound(BHSound):

    # Custom properties
    nchannels = property(fget=lambda self: self.shape[1] if self.ndim > 1 else 1,
                         doc='The number of channels in the sound.')
    nyquist_frequency = property(fget=lambda self: self.samplerate / 2,
                                 doc='The maximum frequency possible in the sound.')

    def __new__(cls, data, *args, **kwargs):

        return BHSound.__new__(cls, data, *args, **kwargs)

    def __init__(self, data, *args, **kwargs):

        self.annotations = dict()
        if isinstance(data, str):
            self.annotate(original_filename=data)

        self.annotate(max_frequency=self.nyquist_frequency,
                      min_frequency=0)

        if isinstance(data, self.__class__):
            self.annotate(**data.annotations)
            self.__dict__.update(data.__dict__)

        if "id" not in self.__dict__:
            self.get_id()

    def __add__(self, other):

        from pecking.combined_sounds import CombinedSound
        if self.duration != other.duration:
            print("Duration of the summed sounds must be identical")
            return
        summed = super(self.__class__, self).__add__(other)
        summed = CombinedSound(summed, [self, other])

        return summed

    def __getitem__(self, key):

        sliced = Sound(super(self.__class__, self).__getitem__(key))
        sliced.__dict__.update(self.__dict__)
        return sliced

    def _newid(self):

        try:
            self.__dict__.pop("id")
        except KeyError:
            pass

    def _getid(self):

        self.id = new_id()

    def annotate(self, **annotations):

        _check_annotations(annotations)
        self.annotations.update(annotations)

    def to_mono(self):

        if self.ndim > 1:
            data = self.mean(axis=1)
            data.__dict__ = self.__dict__
            return data

        return self

    def filter(self, frequency_range=None):

        if frequency_range is None:
            frequency_range = [self.min_frequency, self.max_frequency]
        else:
            frequency_range[0] = np.maximum(self.min_frequency, frequency_range[0])
            frequency_range[1] = np.minimum(self.max_frequency, frequency_range[1])

        if np.all(np.equal(frequency_range, [self.min_frequency, self.max_frequency])):
            return self

        if frequency_range[0] == 0:
            if frequency_range[1] < self.nyquist_frequency:
                filt = lambda self: lowpass_filter(self, frequency_range[1])
        elif frequency_range[1] == self.nyquist_frequency:
            filt = lambda self: highpass_filter(self, frequency_range[0])
        else:
            filt = lambda self: bandpass_filter(self, frequency_range[0], frequency_range[1])

        data = list()
        for ch in xrange(self.nchannels):
            data.append(filt(self.channel(ch)))

        data = self.__class__(data, samplerate=self.samplerate)
        data.annotate(**self.annotations)
        data.annotate(min_freqeuncy=frequency_range[0],
                      max_frequency=frequency_range[1])

        return data

    def pad(self, duration, start=None, max_start=None, min_start=0, make_combined=False, newid=False):

        silence = Sound.silence(float(duration) * second, samplerate=self.samplerate, nchannels=self.nchannels)
        if start is None:
            if max_start is None:
                max_start = float(duration) - float(self.duration)
            start = np.random.uniform(float(min_start), np.minimum(float(max_start), float(silence.duration - self.duration))) * second

        stop = start + self.duration
        silence[start:stop] += self
        silence.start_time = start
        silence.end_time = stop
        silence.annotate(**self.annotations)
        if newid:
            silence._newid()

        return self.__class__(silence)

    def unpad(self, newid=False):

        if newid:
            self._newid()
        return self.__class__(self[self.start_time: self.end_time])

    def embed(self, other, start=None, max_start=None, min_start=0):

        if start is None:
            if max_start is None:
                max_start = np.maximum(float(other.duration - self.duration), 0)
            start = np.random.uniform(float(min_start), float(max_start)) * second

        stop = start + self.duration
        duration = np.maximum(stop, other.duration)
        self = self.pad(duration, start=start)
        other = other.pad(duration, start=0*second)

        return self + other

    def trim(self, duration, trim_from="end", max_start=None):

        if duration >= self.duration:
            return self

        if trim_from == "end":
            trimmed = self[:duration]
        elif trim_from == "start":
            trimmed = self[(self.duration - duration):]
        elif trim_from == "both":
            if max_start is None:
                max_start = self.duration - duration
            start = np.random.uniform(max_start) * brian.second
            start = np.maximum(start, self.duration - duration)
            stop = start + duration
            trimmed = self[start: stop]

        return self.__class__(trimmed)

    @staticmethod
    def query(sounds, query_function):

        if not isinstance(sounds, list):
            sounds = [sounds]

        if isinstance(query_function, list):
            for qf in query_function:
                sounds = [s for s in sounds if qf(s)]
        else:
            sounds = [s for s in sounds if query_function(s)]

        return sounds

    #def sequence(sounds, duration=10*second, ISIs=None):



    # Wrappers for particular sound types
    @classmethod
    def tone(cls, *args, **kwargs):

        return Sound(super(Sound, cls).tone(*args, **kwargs))

    @classmethod
    def harmoniccomplex(cls, *args, **kwargs):

        return Sound(super(Sound, cls).harmoniccomplex(*args, **kwargs))

    @classmethod
    def whitenoise(cls, *args, **kwargs):

        return Sound(super(Sound, cls).whitenoise(*args, **kwargs))

    @classmethod
    def powerlawnoise(cls, *args, **kwargs):

        return Sound(super(Sound, cls).powerlawnoise(*args, **kwargs))

    @classmethod
    def pinknoise(cls, *args, **kwargs):

        return Sound(super(Sound, cls).pinknoise(*args, **kwargs))

    @classmethod
    def brownnoise(cls, *args, **kwargs):

        return Sound(super(Sound, cls).brownnoise(*args, **kwargs))

    @classmethod
    def silence(cls, *args, **kwargs):

        return Sound(super(Sound, cls).silence(*args, **kwargs))

    @classmethod
    def clicks(cls, *args, **kwargs):

        return Sound(super(Sound, cls).clicks(*args, **kwargs))

    @classmethod
    def click(cls, *args, **kwargs):

        return Sound(super(Sound, cls).click(*args, **kwargs))

    @classmethod
    def vowel(cls, *args, **kwargs):

        return Sound(super(Sound, cls).vowel(*args, **kwargs))

    @classmethod
    def irno(cls, *args, **kwargs):

        return Sound(super(Sound, cls).irno(*args, **kwargs))

    @classmethod
    def irns(cls, *args, **kwargs):

        return Sound(super(Sound, cls).irns(*args, **kwargs))
