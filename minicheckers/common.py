#!/usr/bin/env python3
import os.path

def resource(filename):
    '''
    Converts a file path that is relative to the directory where this file is
    located and returns the absolute file path.
    '''
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), filename)
    )
def return_passer(target, callback, *args, **kwargs):
    callback(target(*args, **kwargs))
