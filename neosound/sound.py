from __future__ import division, print_function
import re
import os
import random
from functools import wraps

from matplotlib import pyplot as plt
import numpy as np
from brian import second, hertz, Quantity, units
from brian.hears import dB, dB_type
from brian.hears import Sound as BHSound
from scipy.signal import firwin, filtfilt

try:
    from neo.core.baseneo import _check_annotations
except ImportError:
    from neosound.annotations import _check_annotations
from neosound.sound_manager import *


def create_sound(func):

    @wraps(func)
    def create(*args, **kwargs):
        manager = kwargs.pop("manager", SoundManager())
        created = func(*args, **kwargs)
        created = Sound(created, manager=manager)
        created.manager.store(created, dict(type=CreateTransform,
                                            sound=func.__name__), save=True)
        return created

    return create


class Sound(BHSound):
    '''
    A representation of sounds that inherits and extends the wonderful brian.hears simulator. This is designed to integrate with the python-neo neurophysiology data framework.
    '''

    # Custom properties
    nchannels = property(fget=lambda self: self.shape[1] if self.ndim > 1 else 1,
                         doc='The number of channels in the sound.')
    nyquist_frequency = property(fget=lambda self: self.samplerate / 2,
                                 doc='The maximum frequency possible in the sound.')
    is_silence = property(fget=lambda self: np.all([len(ss) == 0 for ss in self.nonzero()]),
                          doc='A boolean describing if the sound is complete silence.')
    sampleperiod = property(fget=lambda self: 1 / self.samplerate,
                            doc='The time period for each sample (s).')
    ncomponents = property(fget=lambda self: len(self.roots),
                           doc="Number of components of this sound.")
    roots = property(fget=lambda self: self.manager.get_roots(self.id),
                     doc="The ids for each root component of this sound.")

    def __new__(cls, sound, *args, **kwargs):

        kwargs.pop("manager", None)
        kwargs.pop("initialize", None)

        return BHSound.__new__(cls, sound, *args, **kwargs)

    def __init__(self, sound, manager=SoundManager(), initialize=False, **kwargs):

        self.manager = manager
        self.id = self.manager.get_id()

        # Create default attributes
        self.annotations = dict()
        self.transformation = dict()
        self.annotate(samplerate=self.samplerate)

        if isinstance(sound, str):
            self.annotate(original_filename=sound)
            self.manager.store(self, dict(type=LoadTransform,
                                          filename=sound,
                                          samplerate=self.samplerate), save=True)
        if initialize:
            self.manager.store(self, dict(type=InitTransform), save=True)

    def annotate(self, **annotations):

        _check_annotations(annotations)
        self.annotations.update(annotations)
        self.manager.database.store_annotations(self.id, **annotations)

    def __array_wrap__(self, obj, context=None):

        tmp = super(Sound, self).__array_wrap__(obj, context)
        if not hasattr(tmp, "manager") and hasattr(self, "manager"):
            tmp.manager = self.manager
        if not hasattr(tmp, "id") and hasattr(self, "id"):
            tmp.id = self.id
        if context is not None:
            context_type = context[0].__name__
            context_values = context[1]
            in_place = len(context_values) == 3
            # in_place = False
            # Most likely ufunc values are "divide", "multiply", "add", and "subtract"
            used_types = ["divide", "multiply"]
            if context_type in used_types:
                scalar = [val for val in context_values if isinstance(val, (int, float, Quantity))]

                # If this is a multiplication, a scalar would be changing the level
                # Whereas a nonscalar would be something like an envelope
                # Both should be permissible
                if len(scalar):
                    scalar = scalar[0]
                    metadatas = dict(divide=dict(type=MultiplyTransform,
                                                 coefficient=1 / scalar,
                                                 ),
                                     multiply=dict(type=MultiplyTransform,
                                                   coefficient=scalar,
                                                   ))
                    metadata = metadatas[context_type]
                    if in_place:
                        metadata["type"] = InPlaceMultiplyTransform

                    tmp = self.manager.store(tmp, metadata, self)
            #
            #     if len(context_values) == 3:
            #         print("This is an in-place transformation")
            #     else:
            #         print("This transformation creates a new object")
            # #
            # else:
            #     print("Unexpected context type in __array_wrap__: %s" % context_type)

        return tmp

    def __array_finalize__(self, obj):

        super(Sound, self).__array_finalize__(obj)
        self.manager = getattr(obj, "manager", SoundManager())
        self.id = getattr(obj, "id", self.manager.get_id())

    def __getitem__(self, key):

        key = self._rekey(key)
        sliced = super(Sound, self).__getitem__(key)
        if isinstance(key, (int, float, Quantity)):
            return sliced
        else:
            start, stop = self._keydata(key)
            metadata = dict(type=SliceTransform,
                            start_time=float(start),
                            end_time=float(stop),
                            )
            return self.manager.store(sliced, metadata, self)

    def __setitem__(self, key, value):

        key = self._rekey(key)
        start, stop = self._keydata(key)
        metadata = dict(type=SetTransform,
                        start_time=float(start),
                        end_time=float(stop))
        super(Sound, self).__setitem__(key, value)
        return self.manager.store(self, metadata, value)

    def _rekey(self, key):
        if not isinstance(key, (tuple, slice)):
            if isinstance(key, Quantity):
                key *= self.samplerate
                key = int(np.rint(key))
            return key

        channel = slice(None)
        if isinstance(key, tuple):
            channel = key[1]
            key = key[0]

        newkey = [int(np.rint(v * self.samplerate)) if (v is not None) and (units.have_same_dimensions(v, second)) \
                  else v for v in [key.start, key.stop, key.step]]

        return slice(*newkey), channel

    def _keydata(self, key):

        if isinstance(key, (int, float)):
            start = key / self.samplerate
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
                start = key.start / self.samplerate

            if key.stop is None:
                stop = self.duration
            elif units.have_same_dimensions(key.stop, second):
                stop = key.stop
            else:
                stop = key.stop / self.samplerate
        else:
            raise TypeError("__getitem__ key is of an unexpected type: %s." % str(type(key)))

        return start, stop

    def __add__(self, other):
        '''
        Adds together self and other. First it ensures that they have the same duration, which seems like a more
        reasonable default than the brian.hears method of repeating the shorter sound.
        :param other: Another Sound object
        :return: A CombinedSound object that keeps intact the individual sounds in combined.components
        '''

        if self.duration != other.duration:
            print("Duration of the summed sounds must be identical")
            return
        summed = super(Sound, self).__add__(other)
        metadata = dict(type=AddTransform)
        return self.manager.store(summed, metadata, [self, other])

    def __sub__(self, other):

        return self.__add__(-1 * other)

    __iadd__ = __add__
    __isub__ = __sub__

    def set_level(self, level):
        '''
        Sets level in dB SPL (RMS) assuming array is in Pascals. ``level``
        should be a value in dB, or a tuple of levels, one for each channel.
        '''

        rms_dB = self.get_level()
        if self.nchannels>1:
            level = np.array(level)
            if level.size==1:
                level = level.repeat(self.nchannels)
            level = np.reshape(level, (1, self.nchannels))
            rms_dB = np.reshape(rms_dB, (1, self.nchannels))
        else:
            if not isinstance(level, dB_type):
                raise dB_error('Must specify level in dB')
            rms_dB = float(rms_dB)
            level = float(level)
        gain = 10**((level-rms_dB)/20.)

        return self * gain

    def to_mono(self):
        '''
        Converts the Sound object from stereo to mono.
        :return: Mono Sound object
        '''
        if self.ndim > 1:
            metadata = dict(type=MonoTransform)
            data = self.mean(axis=1).reshape((-1, 1))
            return self.manager.store(data, metadata, self)

        return self

    def filter(self, frequency_range=None, filter_order=None):
        '''
        Filters the sound within a particular frequency range. Depending on the values supplied, a lowpass, highpass,
        or bandpass filter will be supplied.
        :param frequency_range: A two element list or tuple with the low and high end of the desired frequency range.
        :return: The filtered Sound object
        '''

        if frequency_range is None:
            return self

        if self.nsamples > 3 * 512:
            filter_order = 512
        elif self.nsamples > 3 * 64:
            filter_order = 64
        else:
            filter_order = 16

        if filter_order * 3 >= self.nsamples:
            raise ValueError("filter_order cannot be greater than nsamples / 3: 3 * %d > %d" % (filter_order, self.nsamples))

        metadata = dict(type=FilterTransform,
                        min_frequency=frequency_range[0],
                        max_frequency=frequency_range[1],
                        order=filter_order)

        if frequency_range[0] == 0:
            if frequency_range[1] < self.nyquist_frequency:
                lowpass = True
                frequency_range = frequency_range[1]
            else:
                return self
        elif frequency_range[1] == self.nyquist_frequency:
            lowpass = False
            frequency_range = frequency_range[0]
        else:
            lowpass = False

        b = firwin(filter_order, frequency_range, nyq=self.nyquist_frequency,
                   pass_zero=lowpass, window="hamming", scale=False)
        a = np.zeros(b.shape)
        a[0] = 1
        data = filtfilt(b, a, self, axis=0)
        # if frequency_range[0] == 0:
        #     if frequency_range[1] < self.nyquist_frequency:
        #         filt = lambda self: lowpass_filter(np.asarray(self).squeeze(), self.samplerate, frequency_range[1], filter_order=filter_order)
        #     else:
        #         return self
        # elif frequency_range[1] == self.nyquist_frequency:
        #     filt = lambda self: highpass_filter(np.asarray(self).squeeze(), self.samplerate, frequency_range[0], filter_order=filter_order)
        # else:
        #     filt = lambda self: bandpass_filter(np.asarray(self).squeeze(), self.samplerate, frequency_range[0], frequency_range[1], filter_order=filter_order)
        #
        # data = list()
        # for ch in xrange(self.nchannels):
        #     data.append(filt(self.channel(ch)))
        #
        return self.manager.store(data, metadata, self)

    def envelope(self, min_power=0*dB):

        env = np.abs(np.asarray(self))

    def to_silence(self):

        return Sound.silence(duration=self.duration, nchannels=self.nchannels, samplerate=self.samplerate)

    def _round_time(self, time):

        return int(time * self.samplerate) * self.sampleperiod

    def pad(self, duration, start=None, max_start=None, min_start=0*second):
        '''
        Pads the sound with silence. All units are in seconds.
        :param duration: Total duration of the resulting sound.
        :param start: Prespecified start time for the Sound object in the silence.
        :param min_start, max_start: Start time will be chosen from a uniform distribution between these two values
        if start is not a provided argument.
        :return: A Sound object with silence applied.
        '''


        if start is None:
            if max_start is None:
                max_start = duration - self.duration
            start = random.uniform(min_start, min(max_start, duration - self.duration))

        # Round times to nearest sample
        duration = self._round_time(duration)
        start = self._round_time(start)

        stop = start + self.duration
        padded = self.extended(duration - stop)
        metadata = dict(type=PadTransform,
                        start_time=start,
                        duration=duration)

        return self.manager.store(padded.shifted(start), metadata, self)

    def unpad(self, threshold=0):

        inds = np.where(np.asarray(self) > threshold)[0]

        return self[inds[0]: inds[-1]]

    def embed(self, other, start=None, max_start=None, min_start=0*second):
        '''
        Embeds the current Sound object in other at a prespecified or random time.
        :param other: A Sound object into which the current Sound object will be embedded
        :param start: Prespecified start time for the Sound object in embedded Sound object
        :param min_start, max_start: Start time will be chosen from a uniform distribution between these two values
        if start is not a provided argument.
        :return: A Sound object with the current Sound object and other Sound object as components
        '''

        if start is None:
            if max_start is None:
                max_start = max(other.duration - self.duration, 0 * second)
            start = random.uniform(min_start, max_start)

        stop = start + self.duration
        duration = max(stop, other.duration)
        padded = self.pad(duration, start=start)
        other = other.pad(duration, start=0*second)

        return padded + other

    def trim(self, duration, trim_from="end", max_start=None, min_start=0*second):
        '''
        Trims a Sound object at a random spot from either the start or end of the sound or both.
        :param duration: Duration of the resulting Sound object
        :param trim_from: Which end of the sound object to trim from. Can be "end", "start", or "both"
        :param min_start, max_start: If trim_from is "both", the start time of the resulting Sound object will be
        chosen from a uniform distribution between these two values.
        :return: A Sound object of the desired duration.
        '''

        if duration >= self.duration:
            return self

        duration = self._round_time(duration)
        if trim_from == "end":
            start = 0 * second
            stop = duration
        elif trim_from == "start":
            start = self.duration - duration
            stop = self.duration
        elif trim_from == "both":
            if max_start is None:
                max_start = self.duration - duration
            start = random.uniform(min_start, max_start)
            start = self._round_time(start)
            start = max(start, self.duration - duration)
            stop = start + duration

        return self[start: stop]

    def clip(self, min_val, max_val):
        # min_val should default to None and then be given the value of negative max_val

        metadata = dict(type=ClipTransform,
                        min_value=min_val,
                        max_value=max_val)
        clipped = super(Sound, self).clip(min_val, max_val)

        return self.manager.store(clipped, metadata, original=self)

    def get_power_nonsilence(self, silence_threshold=.1):

        waveform = np.abs(np.asarray(self))
        range = waveform.max() * silence_threshold
        power = list()
        for ii in xrange(self.nchannels):
            arr = waveform[:, ii].squeeze()
            d = np.diff(arr)
            inds = np.where(np.all(np.vstack([arr[1:-1] > range,
                                              d[:-1] > 0,
                                              d[1:] < 0]),
                                   axis=0))[0]
            power.append((arr[1:-1][inds] ** 2).mean())

        return power

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

    def component(self, n):

        component_id = self.roots[n]

        return self.manager.reconstruct_individual(self.id, component_id)

    @property
    def components(self):

        components = list()
        for root_id in self.roots:
            component_id = self.manager.database.filter_ids(transform_id=self.id,
                                                           transform_root_id=root_id)
            components.extend(component_id)

        return components

    def plot(self):

        plt.plot(self.times, self)
        plt.xlim((0 * second, self.duration))
        plt.xlabel("Time (s)")

    def store(self):

        self.manager.database.store_data(self.id, np.asarray(self))
        self.manager.database.store_annotations(self.id, **self.annotations)

     #def sequence(sounds, duration=10*second, ISIs=None):

    # Wrappers for particular sound types
    @classmethod
    @create_sound
    def tone(cls, *args, **kwargs):

        return super(Sound, cls).tone(*args, **kwargs)

    @classmethod
    @create_sound
    def harmoniccomplex(cls, *args, **kwargs):

        return super(Sound, cls).harmoniccomplex(*args, **kwargs)

    @classmethod
    @create_sound
    def whitenoise(cls, *args, **kwargs):

        return super(Sound, cls).whitenoise(*args, **kwargs)

    @classmethod
    @create_sound
    def powerlawnoise(cls, *args, **kwargs):

        return super(Sound, cls).powerlawnoise(*args, **kwargs)

    @classmethod
    @create_sound
    def pinknoise(cls, *args, **kwargs):

        return super(Sound, cls).pinknoise(*args, **kwargs)

    @classmethod
    @create_sound
    def brownnoise(cls, *args, **kwargs):

        return super(Sound, cls).brownnoise(*args, **kwargs)

    @classmethod
    @create_sound
    def silence(cls, *args, **kwargs):

        return super(Sound, cls).silence(*args, **kwargs)

    @classmethod
    @create_sound
    def clicks(cls, *args, **kwargs):

        return super(Sound, cls).clicks(*args, **kwargs)

    @classmethod
    @create_sound
    def click(cls, *args, **kwargs):

        return super(Sound, cls).click(*args, **kwargs)

    @classmethod
    @create_sound
    def vowel(cls, *args, **kwargs):

        return super(Sound, cls).vowel(*args, **kwargs)

    @classmethod
    @create_sound
    def irno(cls, *args, **kwargs):

        return super(Sound, cls).irno(*args, **kwargs)

    @classmethod
    @create_sound
    def irns(cls, *args, **kwargs):

        return super(Sound, cls).irns(*args, **kwargs)


if False:
    sm = SoundManager(HDF5Store, "/tmp/test.h5")
    shaping = "/auto/k8/tlee/songs/shaping_songs/Track1long.wav"
    s = Sound(shaping, manager=sm)
    w = Sound.whitenoise(duration=s.duration, nchannels=s.nchannels, samplerate=s.samplerate, manager=sm)
    t = Sound.tone(frequency=1000*hertz, duration=s.duration, nchannels=s.nchannels, samplerate=s.samplerate,
                   manager=sm)
    x = w[1*second:3*second]
    s[:x.duration] = x
    y = s + t
    z = y.pad(10*second)
    c = z.component(0)