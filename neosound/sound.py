from __future__ import division, print_function
import re
import os
import random
from functools import wraps
import numpy as np
from brian import second, hertz, Quantity, units
from brian.hears import dB
from brian.hears import Sound as BHSound
from lasp.signal import lowpass_filter, bandpass_filter, highpass_filter
try:
    from neo.core.baseneo import _check_annotations
except ImportError:
    from neosound.annotations import _check_annotations
from neosound.sound_manager import *
import inspect

keep_properties = ["samplerate",
                   "start_time",
                   "end_time",
                   "components",
                   ]


def reinitialize(func):
    '''
    Reinitializes the first output of the function func as a Sound object and if more outputs exist, attempts to
    keep the
    metadata from the last output.
    '''

    @wraps(func)
    def reinitialize_sound(*args, **kwargs):
        output = func(*args, **kwargs)
        if not isinstance(output, tuple):
            return Sound(output, manager=sm)
        elif len(output) == 2:
            return Sound(output[0], manager=sm, keep_metadata=output[-1])
        else:
            return Sound(output[0], manager=sm, keep_metadata=output[-1]), output[1:-1]
    return reinitialize_sound


class Sound(BHSound):
    '''
    A representation of sounds that inherits and extends the wonderful brian.hears simulator. This is designed to
    integrate with the python-neo neurophysiology data framework.
    '''

    # Custom properties
    nchannels = property(fget=lambda self: self.shape[1] if self.ndim > 1 else 1,
                         doc='The number of channels in the sound.')
    nyquist_frequency = property(fget=lambda self: self.samplerate / 2,
                                 doc='The maximum frequency possible in the sound.')
    is_silence = property(fget=lambda self: np.all([len(ss) == 0 for ss in self.nonzero()]),
                          doc='A boolean describing the sound is complete silence.')
    sampleperiod = property(fget=lambda self: 1 / self.samplerate,
                            doc='The time period for each sample (s).')
    ncomponents = property(fget=lambda self: len(self.components),
                           doc="Number of components of this combined sound.")

    def __new__(cls, sound, *args, **kwargs):

        kwargs.pop("merge_metadata", None)
        kwargs.pop("manager", None)
        kwargs.pop("components", None)

        return BHSound.__new__(cls, sound, *args, **kwargs)

    def __init__(self, sound, manager=None, components=list(), merge_metadata=None, **kwargs):
        '''
        :param data: Can be either a string referencing an audio filename or a previous Sound object or a numpy array /
        list of arrays representing a sound waveform.
        :param manager: The sound manager object used to manage IDs, querying, and any other file IO.
        :param keep_metadata: An optional named argument from which sound metadata will also be taken.
        '''

        # Sound manager is optional but necessary for storage of data
        self.manager = manager
        if self.manager:
            self.id = self.manager.get_id()
        else:
            self.id = None

        # Create default attributes
        self.annotations = dict()
        self.components = list()
        self.start_time = 0 * second
        self.end_time = self.duration

        # Depending on the type of input, initialize the Sound object
        if isinstance(sound, self.__class__):
            # Ensure that the sound object has necessary attributes
            if not hasattr(sound, "annotations"):
                sound.annotations = dict()
            if not hasattr(sound, "components"):
                sound.components = list()
            # SoundTransform merges metadata from previous instance
            transform = SoundTransform(self, sound)
            transform.transform()
            if hasattr(sound, "components"):
                components.extend(sound.components)

        else:
            # Initialize with new metadata
            if isinstance(sound, str):
                self.annotate(original_filename=sound)

            self.annotate(max_frequency=self.nyquist_frequency,
                          min_frequency=0 * hertz,
                          original_start_time=0 * second,
                          original_end_time=self.duration,
                          original_id=self.id,
                          components=list(),
                          component_ids=list(),
                          **kwargs)

        self._add_components(components)

        # Add metadata from Sound object in kwargs["keep_metadata"] if it exists
        if merge_metadata is not None:
            transform = SoundTransform(self, merge_metadata)
            transform.transform()

    def annotate(self, **annotations):

        _check_annotations(annotations)
        self.annotations.update(annotations)

    def __getitem__(self, key):

        key = self._rekey(key)
        if self.ncomponents > 0:
            for ii in xrange(self.ncomponents):
                component = self.component(ii)
                sliced = super(Sound, component).__getitem__(key)
                transform = SliceTransform(sliced, component)
                component = transform.transform(key)
                try:
                    summed += component
                except NameError:
                    summed = component

            return summed
        else:
            sliced = super(Sound, self).__getitem__(key)
            transform = SliceTransform(sliced, self)

            return transform.transform(key)

    def __setitem__(self, key, value):

        key = self._rekey(key)
        super(Sound, self).__setitem__(key, value)
        components = list()
        if isinstance(key, (int, float, Quantity)):
            components.append(self.__getitem__(key))
        elif isinstance(key, (slice, tuple)):
            channel = slice(None)
            if isinstance(key, tuple):
                channel = key[1]
                key = key[0]
            segments = self._get_segments(key.start or 0, key.stop or len(self))
            components = list()
            for s1, s2 in segments:
                component = self.__getitem__((slice(s1, s2), channel))
                if s1 == (key.start or 0):
                    component._delete_components()
                transform = ShiftTransform(component)
                components.append(transform.transform(start=s1*self.sampleperiod))
        self._delete_components()
        self._add_components(components)

    def _rekey(self, key):
        if not isinstance(key, (tuple, slice)):
            if isinstance(key, Quantity):
                key *= self.sampleperiod
                key = int(np.rint(key))
            return key

        channel = slice(None)
        if isinstance(key, tuple):
            channel = key[1]
            key = key[0]

        newkey = [int(np.rint(v * self.samplerate)) if (v is not None) and (units.have_same_dimensions(v, second)) \
                  else v for v in [key.start, key.stop, key.step]]

        return slice(*newkey), channel

    def _get_segments(self, start, stop):

        if units.have_same_dimensions(start, second):
            start *= self.samplerate
        if units.have_same_dimensions(stop, second):
            stop *= self.samplerate

        segment_end_points = [0, start, stop, len(self)]
        return [(s1, s2) for s1, s2 in zip(segment_end_points[:-1], segment_end_points[1:]) if s2 > s1]

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
        # return inspect.stack()

        return self.__class__(summed, components=[self, other])

    def __iadd__(self, other):

        return self.__add__(other)

    def to_mono(self):
        '''
        Converts the Sound object from stereo to mono.
        :return: Mono Sound object
        '''
        if self.ndim > 1:
            data = self.mean(axis=1).reshape((-1, 1))
            transform = SoundTransform(data, self)
            return transform.transform()

        return self

    def filter(self, frequency_range=None):
        '''
        Filters the sound within a particular frequency range. Depending on the values supplied, a lowpass, highpass,
        or bandpass filter will be supplied.
        :param frequency_range: A two element list or tuple with the low and high end of the desired frequency range.
        :return: The filtered Sound object
        '''

        if frequency_range is None:
            frequency_range = [self.min_frequency, self.max_frequency]
        else:
            frequency_range[0] = max(self.min_frequency, frequency_range[0])
            frequency_range[1] = min(self.max_frequency, frequency_range[1])

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

        # Create a Sound object using a list of sound channels
        data = self.__class__(data, samplerate=self.samplerate, keep_metadata=self)
        data.annotate(min_freqeuncy=frequency_range[0],
                      max_frequency=frequency_range[1])

        return data

    def pad(self, duration, start=None, max_start=None, min_start=0*second):
        '''
        Pads the sound with silence. All units are in seconds.
        :param duration: Total duration of the resulting sound.
        :param start: Prespecified start time for the Sound object in the silence.
        :param min_start, max_start: Start time will be chosen from a uniform distribution between these two values
        if start is not a provided argument.
        :return: A CombinedSound object with silence applied.
        '''

        if start is None:
            if max_start is None:
                max_start = duration - self.duration
            start = random.uniform(min_start, min(max_start, duration - self.duration))

        stop = start + self.duration
        padded = self.extended(duration - stop)
        self.start_time = start
        self.end_time = stop

        return self.__class__(padded.shifted(start), components=[self])

    def unpad(self):

        return self[self.start_time: self.end_time]

    def embed(self, other, start=None, max_start=None, min_start=0*second):
        '''
        Embeds the current Sound object in other at a prespecified or random time.
        :param other: A Sound object into which the current Sound object will be embedded
        :param start: Prespecified start time for the Sound object in embedded Sound object
        :param min_start, max_start: Start time will be chosen from a uniform distribution between these two values
        if start is not a provided argument.
        :return: A CombinedSound object with the current Sound object and other Sound object as components
        '''

        if start is None:
            if max_start is None:
                max_start = max(other.duration - self.duration, 0 * second)
            start = random.uniform(min_start, max_start)

        stop = start + self.duration
        duration = max(stop, other.duration)
        self = self.pad(duration, start=start)
        other = other.pad(duration, start=0*second)

        return self + other

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
            start = max(start, self.duration - duration)
            stop = start + duration

        return self[start: stop]

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

    def component(self, n, padded=True):

        component = self.components[n]
        if component.duration < self.duration:
            if padded:
                component = component.pad(self.duration,
                                          start=component.start_time)

        return component

    def _add_components(self, components, offset=0*second):

        for component in components:
            transform = ShiftTransform(component)
            component = transform.transform(start=offset)

            # If the individual components are also combinations...
            if component.ncomponents > 0:
                # all of the sub-components need to be offset by this CombinedSound's start_time
                self._add_components(component.components, component.start_time)
            else:
                self._add_component(component)

    def _add_component(self, component):

        # No need to add silent components
        if component.is_silence:
            return
        if component.end_time - component.start_time != component.duration:
            component = component.unpad()

        component_dict = self._annotate_component(component)
        # Check if this component's id exists...
        # if component_dict["id"] in self.annotations["component_ids"]:
        #     # and if so try to merge.
        #     merged = self._merge_component(component_dict, component)
        # else:
        merged = False

        # If it wasn't merged into another component, then add it.
        if not merged:
            self.components.append(component)
            self.annotations["components"].append(component_dict)
            self.annotations["component_ids"].append(component_dict["id"])

    def _delete_components(self):

        self.components = list()
        self.annotations["components"] = list()
        self.annotations["component_ids"] = list()


    def _merge_component(self, other_dict, other, merged=False):
        """
        If all of the values in other match the values of an existing component annotation and the start or end time
        of the existing one is adjacent to start or end time of the new one, then merge them.
        :return: Boolean stating if the components were merged
        """

        new_merge = False

        is_contiguous = lambda s2, e1: (s2 - e1) <= self.sampleperiod

        def is_equal(a, b):
            try:
                return (len(a) == len(b)) and all((a[jj] == b[jj] for jj in xrange(len(a))))
            except TypeError:
                return a == b

        def merge(first, second, first_dict, second_dict):

            first_dict["end_time"] = second_dict["end_time"]
            first_dict["original_end_time"] = second_dict["original_end_time"]
            first = Sound(np.vstack([first, second]), first.manager, keep_metadata=first)

            self.components.append(first)
            self.annotations["components"].append(first_dict)
            self.annotations["component_ids"].append(first_dict["id"])

            return first_dict, first

        count = self.annotations["component_ids"].count(other_dict["id"])
        prev_index = 0
        for ii in xrange(count):
            is_match = True

            index = self.annotations["component_ids"].index(other_dict["id"], prev_index)
            prev_index = index
            current_dict = self.annotations["components"][index]

            # Check start and end times
            is_match = True
            if (is_contiguous(current_dict["original_start_time"], other_dict["original_end_time"]) and
                is_contiguous(current_dict["start_time"], other_dict["end_time"])):
                order = [1, 0]

            elif (is_contiguous(other_dict["original_start_time"], current_dict["original_end_time"]) and
                  is_contiguous(other_dict["start_time"], current_dict["end_time"])):
                order = [0, 1]

            else:
                continue

            # Check if all other values match
            for key in other_dict:
                if key not in ["start_time", "end_time", "original_start_time", "original_end_time"]:
                    if not is_equal(current_dict[key], other_dict[key]):
                        is_match = False
                        break

            if is_match:
                new_merge = True

                current = self.components.pop(index)
                current_dict = self.annotations["components"].pop(index)
                self.annotations["component_ids"].pop(index)

                first, second = [(current, other)[ii] for ii in order]
                first_dict, second_dict = [(current_dict, other_dict)[ii] for ii in order]

                current_dict, current = merge(first, second, first_dict, second_dict)
                break

        if new_merge and (count > 1):
            self._merge_component(current_dict, current, new_merge)

        return merged or new_merge


    def _annotate_component(self, component):
        '''
        Need to store any and all information that can take a component from its original Sound object form and turn
        it into the actual component of the CombinedSound object.
        The relevant parameters are:
        id: the original sound's id
        start_time: the start time of the component in the CombinedSound object
        end_time: the end time of the component in the CombinedSound object
        original_start_time: the start time of the component from the original Sound object
        original_end_time: the end time of the component from the original Sound object
        level: the sound level(s) for each channel
        min_frequency: the minimum frequency of the sound in case any filtering has been done
        max_frequency: the maximum frequency of the sound in case any filtering has been done
        other parameters will include: ramps, resampling, envelope?
        '''

        if "original_id" in component.annotations:
            orig_id = component.annotations["original_id"]
        else:
            orig_id = component.id

        component_dict = dict(id=orig_id,
                              start_time=component.start_time,
                              end_time=component.end_time,
                              original_start_time=component.annotations["original_start_time"],
                              original_end_time=component.annotations["original_end_time"],
                              level=component.level,
                              min_frequency=component.annotations["min_frequency"],
                              max_frequency=component.annotations["max_frequency"],
                              )

        return component_dict


    #def sequence(sounds, duration=10*second, ISIs=None):



    # Wrappers for particular sound types
    @classmethod
    @reinitialize
    def tone(cls, *args, **kwargs):

        return super(Sound, cls).tone(*args, **kwargs)

    @classmethod
    @reinitialize
    def harmoniccomplex(cls, *args, **kwargs):

        return super(Sound, cls).harmoniccomplex(*args, **kwargs)

    @classmethod
    @reinitialize
    def whitenoise(cls, *args, **kwargs):

        return super(Sound, cls).whitenoise(*args, **kwargs)

    @classmethod
    @reinitialize
    def powerlawnoise(cls, *args, **kwargs):

        return super(Sound, cls).powerlawnoise(*args, **kwargs)

    @classmethod
    @reinitialize
    def pinknoise(cls, *args, **kwargs):

        return super(Sound, cls).pinknoise(*args, **kwargs)

    @classmethod
    @reinitialize
    def brownnoise(cls, *args, **kwargs):

        return super(Sound, cls).brownnoise(*args, **kwargs)

    @classmethod
    @reinitialize
    def silence(cls, *args, **kwargs):

        return super(Sound, cls).silence(*args, **kwargs)

    @classmethod
    @reinitialize
    def clicks(cls, *args, **kwargs):

        return super(Sound, cls).clicks(*args, **kwargs)

    @classmethod
    @reinitialize
    def click(cls, *args, **kwargs):

        return super(Sound, cls).click(*args, **kwargs)

    @classmethod
    @reinitialize
    def vowel(cls, *args, **kwargs):

        return super(Sound, cls).vowel(*args, **kwargs)

    @classmethod
    @reinitialize
    def irno(cls, *args, **kwargs):

        return super(Sound, cls).irno(*args, **kwargs)

    @classmethod
    @reinitialize
    def irns(cls, *args, **kwargs):

        return super(Sound, cls).irns(*args, **kwargs)


if True:
    sm = SoundManager()
    shaping = "/auto/k8/tlee/songs/shaping_songs/Track1long.wav"
    s = Sound(shaping)
    w = Sound.whitenoise(duration=s.duration, nchannels=s.nchannels, samplerate=s.samplerate)