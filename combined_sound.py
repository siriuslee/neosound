import os
import numpy as np
from brian import *
from brian.hears import dB
from pecking.sound import Sound

class CombinedSound(Sound):

    ncomponents = property(fget=lambda self: len(self.components),
                           doc="Number of components of this combined sound.")

    def __new__(cls, sound, components, *args, **kwargs):

        return super(CombinedSound, cls).__new__(cls, sound, *args, **kwargs)

    def __init__(self, sound, components):

        if "components" not in sound.__dict__:
            self.components = list()

        self._add_components(components)


    def __getitem__(self, key):

        start = float(key.start) * second or 0 * second
        stop = float(key.stop) * second or 0 * second
        sliced = super(CombinedSound, self).__getitem__(key)
        components = list()
        for ii in xrange(self.ncomponents):
            component = self.component(ii)
            cstart, cstop = component.start_time, component.end_time
            component = component.__getitem__(key)
            component.start_time = np.maximum(cstart - start, 0)
            component.end_time = np.minimum(cstop, stop)
            component = component.unpad()
            components[ii] = component

        return CombinedSound(sliced, components)

    def component(self, n, padded=True):

        component = self.components[n]
        if component.duration < self.duration:
            if padded:
                component = component.pad(self.duration,
                                          start=component.start_time)

        return component

    def _add_components(self, components, offset=0):

        for component in components:
            if isinstance(component, CombinedSound):
                if "start_time" in component.__dict__:
                    start_time = component.start_time
                else:
                    start_time = 0
                self._add_components(component.componenents, offset + start_time)
            else:
                self._add_component(component, offset)

    def _add_component(self, component, offset=0):

        if "start_time" not in component.__dict__:
            component.start_time = offset
        if "end_time" not in component.__dict__:
            component.end_time = offset + component.duration
        if component.end_time - component.start_time != component.duration:
            component = component.unpad()

        self.components.append(component)
