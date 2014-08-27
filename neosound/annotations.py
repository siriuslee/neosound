import numpy as np
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from numbers import Number

ALLOWED_ANNOTATION_TYPES = (int, float, complex,
                            str, bytes,
                            type(None),
                            datetime, date, time, timedelta,
                            Number, Decimal,
                            np.number, np.bool_)

def _check_annotations(value):
    """
    Recursively check that value is either of a "simple" type (number, string,
    date/time) or is a (possibly nested) dict, list or numpy array containing
    only simple types.
    """

    if isinstance(value, np.ndarray):
        if not issubclass(value.dtype.type, ALLOWED_ANNOTATION_TYPES):
            raise ValueError("Invalid annotation. NumPy arrays with dtype %s"
                             "are not allowed" % value.dtype.type)
    elif isinstance(value, dict):
        for element in value.values():
            _check_annotations(element)
    elif isinstance(value, (list, tuple)):
        for element in value:
            _check_annotations(element)
    elif not isinstance(value, ALLOWED_ANNOTATION_TYPES):
        raise ValueError("Invalid annotation. Annotations of type %s are not"
                         "allowed" % type(value))


def merge_annotation(a, b):
    """
    First attempt at a policy for merging annotations (intended for use with
    parallel computations using MPI). This policy needs to be discussed
    further, or we could allow the user to specify a policy.

    Current policy:
        For arrays or lists: concatenate
        For dicts: merge recursively
        For strings: concatenate with ';'
        Otherwise: fail if the annotations are not equal
    """
    assert type(a) == type(b), 'type(%s) %s != type(%s) %s' % (a, type(a),
                                                               b, type(b))
    if isinstance(a, dict):
        return merge_annotations(a, b)
    elif isinstance(a, np.ndarray):  # concatenate b to a
        return np.append(a, b)
    elif isinstance(a, list):  # concatenate b to a
        return a + b
    elif isinstance(a, basestring):
        if a == b:
            return a
        else:
            return a + ";" + b
    else:
        assert a == b, '%s != %s' % (a, b)
        return a


def merge_annotations(A, B):
    """
    Merge two sets of annotations.

    Merging follows these rules:
    All keys that are in A or B, but not both, are kept.
    For keys that are present in both:
        For arrays or lists: concatenate
        For dicts: merge recursively
        For strings: concatenate with ';'
        Otherwise: fail if the annotations are not equal
    """
    merged = {}
    for name in A:
        if name in B:
            try:
                merged[name] = merge_annotation(A[name], B[name])
            except BaseException as exc:
                exc.args += ('key %s' % name,)
                raise
        else:
            merged[name] = A[name]
    for name in B:
        if name not in merged:
            merged[name] = B[name]

    return merged
