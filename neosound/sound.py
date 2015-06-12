from __future__ import division, print_function
import random
from functools import wraps
from matplotlib import pyplot as plt
from scipy.signal import firwin, filtfilt, resample
import numpy as np

from brian import Quantity, msecond
from brian.hears import Sound as BHSound
from brian.hears import dB_type, dB_error

try:
    from neo.core.baseneo import _check_annotations
except ImportError:
    from neosound.annotations import _check_annotations
from neosound.sound_manager import *
from neosound.sound_transforms import *
from neosound.sound_store import *

def store_transformation(func):
    '''
    Every function that should store transform parameters will output a tuple of the format
    (transformed object, other outputs, transform metadata). The transformed object and other outputs will be
    returned and the metadata will be stored. Adding a read_only=True keyword to the function call will prevent the
    metadata from being stored.
    '''

    @wraps(func)
    def funcwrap(obj, *args, **kwargs):
        read_only = kwargs.pop("read_only", False)
        try:
            result = func(obj, *args, **kwargs)
        except UnprocessedError as e:
            # print(e)
            return obj

        transformed = result[0]
        metadata = result[-1]

        # try to write
        if not read_only:
            obj.manager.store(transformed, metadata, obj)

        if len(result) > 2:
            transformed = (transformed, ) + result[1: -1]

        return transformed

    return funcwrap

def create_sound(func):
    """
    Wraps all sound creation methods so that they inherit the documentation from upstream BHSound methods
    """

    @wraps(func)
    def funcwrap(cls, *args, **kwargs):
        manager = kwargs.pop("manager", SoundManager())
        created = func(cls, *args, **kwargs)
        metadata = dict(type=CreateTransform,
                        sound=func.__name__)
        for kw, val in kwargs.iteritems():
            if isinstance(val, Quantity):
                metadata["%s_units" % kw] = repr(val.dim)
                val = float(val)
            metadata[kw] = val
        created = Sound(created, manager=manager)
        created.manager.store(created, metadata)
        created.store()
        return created

    funcwrap.__doc__ = getattr(BHSound, func.__name__, func).__doc__

    return funcwrap

def ensure_type(func):
    """
    Ensures that all BHSound objects are converted to Sound objects
    """

    @wraps(func)
    def funcwrap(obj, *args, **kwargs):
        result = func(obj, *args, **kwargs)
        if isinstance(result, tuple):
            result = list(result) # tuples are immutable. Convert to list first.
            for ii, rr in enumerate(result):
                if isinstance(rr, (BHSound, np.ndarray)): # Why ndarray? Wouldn't it fail since I'm not providing a samplerate?
                    result[ii] = Sound(rr, manager=obj.manager)
            result = tuple(result)
        else:
            if isinstance(result, (BHSound, np.ndarray)):
                result = Sound(result, manager=obj.manager)

        return result

    return funcwrap


class Sound(BHSound):
    """
    A representation of sounds that inherits and extends the wonderful brian.hears simulator.
    """

    # Class values
    stored_methods = ["clip", "combine", "filter", "pad", "ramp", "replace", "resample", "set_level", "slice",
                      "to_mono"]

    # Custom properties
    nchannels = property(fget=lambda self: self.shape[1] if self.ndim > 1 else 1,
                         doc='The number of channels in the sound.')
    nyquist_frequency = property(fget=lambda self: self.samplerate / 2,
                                 doc='The maximum frequency possible in the sound.')
    sampleperiod = property(fget=lambda self: 1 / self.samplerate,
                            doc='The time period for each sample (s).')
    ncomponents = property(fget=lambda self: len(self.roots),
                           doc="Number of components of this sound.")
    roots = property(fget=lambda self: self.manager.get_roots(self.id),
                     doc="The ids for each root component of this sound.")

    def __new__(cls, sound, *args, **kwargs):

        for kw in ["manager", "initialize", "save"]:
            kwargs.pop(kw, None)

        return BHSound.__new__(cls, sound, *args, **kwargs)

    def __init__(self, sound, samplerate=None, manager=None, save=True, initialize=False, **kwargs):
        """
        Creates a Sound object that contains a lot of useful information about the waveform, as well as methods that
        allow for quick manipulations and visualizations.
        :param sound: contains the waveform data. Can be a Sound object, a filename, or a numpy array.
        :param samplerate: the samplerate of the sound in units of hertz. Only required if "sound" is a numpy array
        :param manager: an instance of SoundManager. If None, the default manager will be used.
        :param save: If sound is a filename, whether or not to save the waveform data to the database
        :param initialize: Stores the newly created Sound object as an InitTransform
        :param kwargs: All additional keyword arguments will be added as annotations to the sound object
        :return: an instance of Sound
        """

        if manager is None:
            if hasattr(sound, "manager"):
                self.manager = sound.manager
            else:
                self.manager = SoundManager()
        else:
            self.manager = manager

        self.id = self.manager.get_id()

        if hasattr(sound, "samplerate"):
            self.samplerate = sound.samplerate

        # Initialize annotations
        self.annotations = dict()
        self.annotate(samplerate=float(self.samplerate), **kwargs)

        if isinstance(sound, str):
            self.annotate(original_filename=sound)
            self.manager.store(self, dict(type=LoadTransform,
                                          filename=sound,
                                          samplerate=float(self.samplerate)))
            if save:
                self.store()
        # Do I really need this?
        if initialize:
            self.manager.store(self, dict(type=InitTransform))
            self.store()

    def annotate(self, **annotations):
        """
        Add an annotation to the sound
        :param annotations: comma-separated key-value pairs to be added to the sound objects annotations. All values
        are also stored in the database.

        Example:
        sound.annotate(type="sentence", transcript="This is a test")
        sound.annotations["type"]
        sound.annotations["transcript"]
        """

        _check_annotations(annotations)
        self.annotations.update(annotations)
        self.manager.database.store_annotations(self.id, **annotations)

    def update_annotations(self):
        """
        Updates the annotation dictionary according to what is in the database. These will almost always be the same.
        :return: True if the annotations didn't change, else False.
        """

        prev_annotations = self.annotations
        self.annotations = self.manager.database.get_annotations(self.id)

        return prev_annotations == self.annotations

    def detail(self):
        """
        Currently just returns the transformation metadata that led to this sound object. Future versions may improve on this.
        :return: dictionary of transformation metadata
        """

        return self.manager.get_transformation_metadata(self.id)

    def asarray(self):
        """
        Get the waveform data for the sound as a numpy array.
        """

        return np.squeeze(np.asarray(self))

    # def __array_wrap__(self, obj, context=None):
    #
    #     tmp = super(Sound, self).__array_wrap__(obj, context)
    #     if not hasattr(tmp, "manager") and hasattr(self, "manager"):
    #         tmp.manager = self.manager
    #     if not hasattr(tmp, "id") and hasattr(self, "id"):
    #         tmp.id = self.id
    #
    #     return tmp
    #
    # def __array_finalize__(self, obj):
    #
    #     super(Sound, self).__array_finalize__(obj)
    #     self.manager = getattr(obj, "manager", SoundManager())
    #     self.id = getattr(obj, "id", self.manager.get_id())

    def __add__(self, other):
        """
        BHSound does not require that self and other be of the same length. If they are not, then it tiles the
        shorter one. This seems to not be the best default, so I'm overriding it such that the sounds must be of the
        same length.
        """

        if self.duration != other.duration:
            raise ValueError("Duration of the summed sounds must be identical: %3.2f != %3.2f" % (self.duration, other.duration))

        return super(Sound, self).__add__(other)

    def __sub__(self, other):

        return self.__add__(-1 * other)

    __iadd__ = __add__
    __radd__ = __add__
    __isub__ = __sub__
    __rsub__ = __sub__

    def _round_time(self, time):
        """
        Rounds time to the nearest sample
        :param time: time point (seconds or samples)
        :return: time point (s) that is nearest to "time" and falls on a sample
        """
        if isinstance(time, Quantity):
            time = int(time * self.samplerate) * self.sampleperiod
        else:
            time = time * self.sampleperiod

        return time

    @store_transformation
    @ensure_type
    def clip(self, max_val, min_val=None):
        """
        Clips the peaks of the sound at the specified values
        :param max_val: the maximum value for the resulting sound
        :param min_val: the minimum value for the resulting sound. If none is specified it will be -max_val.
        :return: A Sound object where everything above max_val is set to max_val and everything below min_val is set
        to min_val
        """

        # set default min_val
        if min_val is None:
            min_val = -max_val

        clipped = super(Sound, self).clip(min_val, max_val)

        metadata = dict(type=ClipTransform,
                        min_value=float(min_val),
                        max_value=float(max_val))
        return clipped, metadata

    @store_transformation
    @ensure_type
    def combine(self, other):
        '''
        Adds together self and other.
        :param other: Another Sound object
        :return The summed Sound object
        '''
        summed = self + other

        metadata = dict(type=AddTransform,
                        parents=[self.id, other.id])
        return summed, metadata

    @store_transformation
    @ensure_type
    def filter(self, frequency_range, filter_order=None):
        '''
        Filters the sound within a particular frequency range. Depending on the values supplied, a lowpass, highpass,
        or bandpass filter will be supplied.
        :param frequency_range: A two element list or tuple with the low and high end of the desired frequency range.
        :param filter_order: The order of the filter. To be supplied to firwin. Defaults to 512 if nsamples > 3 *
        512, 64 if nsamples > 3 * 64, else 16. Value cannot be greater than nsamples / 3.
        :return: The filtered Sound object
        '''

        # TODO: Add additional filter types and documentation on how the filtering is done.

        if filter_order is None:
            if self.nsamples > 3 * 512:
                filter_order = 512
            elif self.nsamples > 3 * 64:
                filter_order = 64
            else:
                filter_order = 16

        if filter_order * 3 >= self.nsamples:
            raise ValueError("filter_order cannot be greater than nsamples / 3: 3 * %d > %d" % (filter_order,
                                                                                                self.nsamples))

        if len(frequency_range) == 2:
           if frequency_range[1] > self.nyquist_frequency:
               raise ValueError("frequency_range[1] cannot be greater than the nyquist frequency: %d" % self.nyquist_frequency)
        else:
            raise ValueError("frequency_range must have two elements")

        if frequency_range[0] == 0: # This is a lowpass filter
            if frequency_range[1] < self.nyquist_frequency:
                lowpass = True
                frequency_range = frequency_range[1]
            else: # No filtering should be done
                raise UnprocessedError("No filtering is necessary")
        elif frequency_range[1] == self.nyquist_frequency: # This is a highpass filter
            lowpass = False
            frequency_range = frequency_range[0]
        else: # This is a bandpass filter
            lowpass = False

        # Compute the filter
        b = firwin(filter_order, frequency_range, nyq=self.nyquist_frequency,
                   pass_zero=lowpass, window="hamming", scale=False)
        a = np.zeros(b.shape)
        a[0] = 1

        # Filter the sound
        data = filtfilt(b, a, self, axis=0)

        metadata = dict(type=FilterTransform,
                        min_frequency=float(frequency_range[0]),
                        max_frequency=float(frequency_range[1]),
                        order=filter_order)
        return data, metadata

    @store_transformation
    @ensure_type
    def get_channel(self, n):
        """
        Returns the specified channel of the sound
        """

        metadata = dict(type=ChannelTransform,
                        channel=n)
        return self.channel(n), metadata

    @store_transformation
    @ensure_type
    def pad(self, duration, start=None, max_start=None, min_start=0*second):
        '''
        Pads the sound with silence. All units are in seconds.
        :param duration: Total duration of the resulting sound.
        :param start: Prespecified start time for the Sound object in the silence. If None, a random time will be
        chosen.
        :param min_start, max_start: Start time will be chosen from a uniform distribution between these two values
        if start is not a provided argument.
        :return A Sound object with silence applied.
        '''

        if duration < self.duration:
            raise UnprocessedError("Sound already has a duration greater than %3.2f" % duration)

        if start is None: # Choose a random start time
            if max_start is None:
                max_start = duration - self.duration
            start = random.uniform(min_start, min(max_start, duration - self.duration))

        # Round times to nearest sample
        duration = self._round_time(duration)
        start = self._round_time(start)

        # Pad the end of the sound
        stop = start + self.duration
        padded = self.extended(duration - stop)

        metadata = dict(type=PadTransform,
                        start_time=float(start),
                        duration=float(duration))
        # Pad the start of the sound and return
        return padded.shifted(start), metadata

    @store_transformation
    @ensure_type
    def ramp(self, when="both", duration=10*msecond, envelope=None):
        '''
        Adds a ramp on/off to the sound

        when='onset' - Can take values 'onset', 'offset' or 'both'
        duration=10*ms - The time over which the ramping happens
        envelope=None - A ramping function, if not specified uses ``sin(pi*t/2)**2``.
        The function should be a function of one variable ``t`` ranging from
        0 to 1, and should increase from ``f(0)=0`` to ``f(0)=1``. The
        reverse is applied for the offset ramp. Currently the default type
        is the only one supported for storage.

        :param when: can take values 'onset', 'offset' or 'both' ('both')
        :param duration: the time over which the ramping happens (10 ms)
        :param envelope: Not currently implemented. A ramping function, if not specified uses ``sin(pi*t/2)**2``. The
        function should be a function of one variable ``t`` ranging from 0 to 1, and should increase from ``f(0)=0``
        to ``f(0)=1``. The reverse is applied for the offset ramp.
        :return: A Sound object with the ramp applied.
        '''

        # TODO: Rewrite this to include other ramp options. Perhaps use scipy's windowing functions.

        ramped = super(Sound, self).ramp(when=when, duration=duration, envelope=envelope, inplace=False)

        metadata = dict(type=RampTransform,
                        when=when,
                        duration=float(duration))
        return ramped, metadata

    @store_transformation
    @ensure_type
    def replace(self, start, stop, other):
        """
        Replaces the values of the sound from start to stop with the values from other.
        :param start: start time index
        :param stop: stop time index
        :param other: a Sound object to replace the current values with.
        :return: A new sound object
        """

        start = self._round_time(start)
        stop = self._round_time(stop)

        if (stop - start) != other.duration:
            raise ValueError("stop - start should be the same as the other sounds' duration. %3.2f != %3.2f" % (stop
                                                                                                                -
                                                                                                                start,
                                                                                                                other.duration))

        new = Sound(self)
        new[start: stop] = other

        metadata = dict(type=SetTransform,
                        start_time=float(start),
                        stop_time=float(stop),
                        parents=[self.id, other.id])
        return new, metadata

    @store_transformation
    @ensure_type
    def resample(self, samplerate=None, resample_type="sinc_best"):
        """
        Returns a resampled version of the sound using scipy.signal.resample.
        :param samplerate: desired output samplerate in hertz
        :param resample_type: the type of resampling. See scipy.signal.resample documentation ("sinc_best")
        :return: A resampled Sound object
        """

        if (samplerate == self.samplerate) or (samplerate is None):
            raise UnprocessedError("Samplerate is already %.1f" % samplerate)

        resampled = resample(self, int(samplerate * self.duration))
        resampled = Sound(resampled, samplerate=samplerate, manager=self.manager)

        metadata = dict(type=ResampleTransform,
                        new_samplerate=float(samplerate),
                        resample_type=resample_type)
        return resampled, metadata

    @store_transformation
    @ensure_type
    def scale(self, c):
        """
        Scales the sound by a factor of c.
        :param c: a coefficient.
        :return: A scaled sound object
        """

        if isinstance(c, dB_type):
            c = c.gain()

        metadata = dict(type=MultiplyTransform,
                        coefficients=c)

        return self * c, metadata

    @store_transformation
    @ensure_type
    def slice(self, start, stop=None):
        """
        Returns a section of the sound from start to stop
        :param start: starting time in seconds
        :param stop: stopping time in seconds (sound duration)
        :return: Sound object of the sliced segment
        """

        if stop is None:
            stop = self.duration

        start = self._round_time(start)
        stop = self._round_time(stop)
        sliced = self[start: stop]

        metadata = dict(type=SliceTransform,
                        start_time=float(start),
                        stop_time=float(stop))
        return sliced, metadata

    @store_transformation
    @ensure_type
    def to_mono(self):
        '''
        Converts the Sound object to mono by averaging the channels.
        :return: Mono Sound object
        '''

        if self.ndim == 1:
            raise UnprocessedError("Sound is already mono")

        data = Sound(self.mean(axis=1).reshape((-1, 1)),
                     samplerate=self.samplerate,
                     manager=self.manager)

        metadata = dict(type=MonoTransform)
        return data, metadata

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

    def embed(self, other, start=None, max_start=None, min_start=0*second, ratio=None):
        '''
        Embeds the current Sound object in other at a prespecified or random time.
        :param other: A Sound object into which the current Sound object will be embedded
        :param start: Prespecified start time for the Sound object in embedded Sound object
        :param min_start, max_start: Start time will be chosen from a uniform distribution between these two values
        if start is not a provided argument.
        :param ratio: The level ratio of self to other in decibels. If None (default), then the levels are left alone
        :return: A Sound object with the current Sound object and other Sound object as components
        '''

        if start is None:
            if max_start is None:
                max_start = max(other.duration - self.duration, min_start)
            start = random.uniform(min_start, max_start)

        stop = start + self.duration
        duration = max(stop, other.duration)
        padded = self.pad(duration, start=start)
        other = other.pad(duration, start=0*second)

        if ratio is not None:
            other = other.set_level(self.level - ratio)

        return padded.combine(other)

    # def envelope(self, min_power=0*dB):
    #
    #     env = np.abs(np.asarray(self))

    def get_power_nonsilence(self, silence_threshold=.1):
        """
        Gets the total amount of power in the nonsilent regions of the sound.
        :param silence_threshold: fraction of max value below which the sound should be considered silent (0.1)
        :return: power
        """

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

    def plot(self):

        plt.plot(self.times, self)
        plt.xlim((0 * second, self.duration))
        plt.xlabel("Time (s)")

    def set_level(self, level):
        """
        Sets level in dB SPL (RMS) assuming array is in Pascals.
        :param level: a value in dB, or a tuple of levels, one for each channel.
        :return: A new Sound object with the specified level
        """

        # TODO: What is the reference intensity?

        # Sound is silent. Scaling it would result in breakage.
        if not np.any(self.asarray() != 0):
            raise UnprocessedError("Sound is silent")

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

        return self.scale(gain)


    def store(self):

        self.manager.database.store_data(self.id, np.asarray(self))
        self.manager.database.store_annotations(self.id, **self.annotations)

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
            start = min(start, self.duration - duration)
            stop = start + duration
        else:
            raise ValueError("Only 'start', 'end', and 'both' are acceptable values for trim_from")

        return self.slice(start, stop)

    def unpad(self, threshold=0):
        """
        Removes the silent regions at the beginning and end of a sound.
        :param threshold: the value at which the sound should no longer be considered silent
        :return: segment of sound with silence removed.
        """

        inds = np.where(np.abs(np.asarray(self)) > threshold)[0]
        start = self._round_time(inds[0])
        stop = self._round_time(inds[-1])

        return self.slice(start, stop)

    @staticmethod
    def query(sounds, query_function):
        """
        Filter a list of sounds according to a given function
        :param sounds: a list of Sound objects
        :param query_function: a function or list of functions to be applied to each object in sounds that returns
        True or False.
        :return: A list of Sound objects where query_function evaluated to True
        """

        if not isinstance(sounds, list):
            sounds = [sounds]

        if isinstance(query_function, list):
            for qf in query_function:
                sounds = [s for s in sounds if qf(s)]
        else:
            sounds = [s for s in sounds if query_function(s)]

        return sounds

    # Wrappers for particular sound types
    @staticmethod
    @create_sound
    def spectrum_matched_noise(spectrum, samplerate=44100*hertz, manager=SoundManager(), save=True):

        if len(spectrum.shape) == 1:
            spectrum = np.reshape(spectrum, -1, 1)

        mag = np.abs(spectrum)
        n = len(mag)
        n2 = int(n / 2)
        phase = np.ones(mag.shape, dtype=complex)
        if n % 2 == 1:
            phase[1: n2 + 1, :] = np.exp(1j * np.random.uniform(-np.pi, np.pi, (n2, phase.shape[1])))
            phase[n2 + 1:, :] = np.flipud(np.conj(phase[1: n2 + 1, :]))
        else:
            phase[1: n2 + 1, :] = np.exp(1j * np.random.uniform(-np.pi, np.pi, (n2, phase.shape[1])))
            phase[n2 + 1:, :] = np.flipud(np.conj(phase[1: n2, :]))

        z = mag * phase
        noise = Sound(np.fft.ifft(z, axis=0).real, samplerate=samplerate, manager=manager)

        return noise

    def to_spectrum_matched_noise(self, duration=None):

        if duration is None:
            duration = self.duration

        next2 = lambda x: 2 ** (np.ceil(np.log2(x)))
        pad_duration = next2(int(duration * self.samplerate)) * self.sampleperiod
        spectrum = np.fft.fft(self.pad(pad_duration, start=0*second), axis=0)

        return Sound.spectrum_matched_noise(spectrum, samplerate=self.samplerate, manager=self.manager).slice(
            0*second, duration).set_level(self.level)

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

    def to_silence(self):

        return Sound.silence(duration=self.duration, nchannels=self.nchannels, samplerate=self.samplerate)

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


class UnprocessedError(Exception):
    pass

