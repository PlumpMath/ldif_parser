#!/usr/bin/env python2


from functools import wraps

def varargs(option, opt_str, value, parser):
    """Recipe for variable arguments

    Because we can't use argparse in python 2.6"""
    assert value is None
    value = []

    def floatable(str):
        try:
            float(str)
            return True
        except ValueError:
            return False

    for arg in parser.rargs:
        if arg[:2] == "--" and len(arg) > 2:
            break
        if arg[:1] == "-" and len(arg) > 1 and not floatable(arg):
            break
        value.append(arg)

    del parser.rargs[:len(value)]
    setattr(parser.values, option.dest, value)

def coroutine(func):
    """Decorator to prime coroutines

    Advances coroutine to first occurence of yield keyword"""
    @wraps(func)
    def prime_it(*args, **kwargs):
        cr = func(*args, **kwargs)
        cr.next()
        return cr
    return prime_it

def clean(lines):
    """Strip whitespace from each line of input data"""
    return (line.strip() for line in lines)

