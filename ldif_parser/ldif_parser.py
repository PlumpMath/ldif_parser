#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
This module parses data extracted from a large corporate
LDAP directory in LDIF format. The module is designed to
analyse LDAP group names and use this information to produce
a CSV report of all group members annotated with metadata
derived from a standard naming convention used for the group name.

The module attempts to solve this problem in a functional
programming style using generators and coroutines. The generators
and coroutines are chained together to create a parsing pipeline
that analyses and manipulates each item of data as it is retrieved
by the 'ldaplist' command.

    get_data -> compile_report -> get_username -> get_fullname

In order to obtain the fullname of the group members, a second
'ldaplist' call is made to retrieve a number of candidate attributes
that might hold the full name data. To help minimize the network IO,
each user's fullname is cached in a dictionary once retrieved from LDAP.
So it only needs to be retrieved from the directory once
even if the user is a member of many LDAP groups.

Mock data is supplied in the mock-data.txt file and is used in
the Unittests. Monkey patching is used to replace the calls
to the OS 'ldaplist' command in the tests.

To run the tests execute:

    python test_ldif_parser.py -v

"""

import re
import shlex
from subprocess import Popen, PIPE
from optparse import OptionParser
from collections import namedtuple
from itertools import chain
from functools import wraps

# NamedTuples

Netgroup = namedtuple('Netgroup', ['groupname', 'grp', 'env', 'role', 'member', 'keep'])
Member = namedtuple('Member', ['userid', 'fullname'])

class InvalidLdifError(Exception):
    """Raise this custom exception for incorrectly formatted LDIF lines"""
    def __init__(self):
        Exception.__init__(self, 'Received invalid LDIF data')

def varargs(option, opt_str, value, parser):
    """recipe for variable arguments because
    we can't use argparse in python 2.6"""
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
    """decorator to prime coroutines, advances coroutine
    to first occurence of yield keyword"""
    @wraps(func)
    def prime_it(*args, **kwargs):
        cr = func(*args, **kwargs)
        cr.next()
        return cr
    return prime_it

def get_data(netgroups):
    """use ldaplist to retrieve LDIF-formatted data from LDAP"""
    cmd = shlex.split('ldaplist -l netgroup {0}'.format(' '.join(netgroups)))
    results = Popen(cmd, stdout=PIPE).communicate()[0].splitlines()
    for line in results:
        yield line

def clean(lines):
    """strip whitespace from each line of input data"""
    return (line.strip() for line in lines)

def ldif_to_tuple(ldif):
    """helper function to convert LDAP data
    from LDIF format to tuple"""
    attr, colon, value = ldif.partition(':')
    if not colon:
        raise InvalidLdifError
    return tuple((attr.strip(), value.strip()))

@coroutine
def get_fullname():
    """lookup fullnames from ldap
    cache the results in a local dict to speed up subsequent lookups"""
    cache = dict()
    fullname_attrs = set(['displayName', 'description', 'gecos'])
    while True:
        userlist, userid = (yield)
        try:
            fullname = cache[userid]
        except KeyError:
            cmd = shlex.split(r'ldaplist -l passwd {userid}'.format(userid=userid))
            user_details = Popen(cmd, stdout=PIPE).communicate()[0].splitlines()
            user_details = imap(ldif_to_tuple, user_details)
            user_names = (
                value for attr, value in user_details
                if attr in fullname_attrs)
            fullname = max(user_names, key=len)
            cache[userid] = fullname
            userlist.append(Member(userid, fullname))

@coroutine
def get_username():
    """use a regex pattern
    to extract the username from a nisNetgroupTriple"""
    username_pattern = re.compile(r',(?P<user>[a-zA-Z0-9]+),')
    find_fullname = get_fullname()
    while True:
        userlist, line = (yield)
        matches = username_pattern.search(line)
        if matches:
            find_fullname.send((userlist, matches.group('user')))

@coroutine
def compile_report():
    """coroutine to process ldif stream"""
    userlist = []
    groupname = ''
    user_builder = get_username()
    while True:
        report_rows, ldif_line = (yield)
        if len(ldif_line) == 0:
            _, company, env, role = groupname.split('_')
            for each_user in userlist:
                report_rows.append(Netgroup(groupname, company, env, role, each_user, 'N'))
            # del userlist
            userlist = []
            groupname = ''
        elif ldif_line.startswith('cn: '):
            groupname = ldif_line.partition(':')[-1].strip()
        elif ldif_line.startswith('nisNetgroup'):
            user_builder.send((userlist, ldif_line))

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-g", "--group", action="callback", callback=varargs, dest="grps")
    options, files = parser.parse_args()

    source = get_data(options.grps)

    report_rows = list()
    report_builder = compile_report()
    for line in clean(source):
        report_builder.send((report_rows, line))
    # flush the last set of data from the co-routine
    # by sending a final blank line - feels clunky!
    report_builder.send((report_rows, ''))

    template = '{0:<16} : {1:<3} : {2:<3} : {3:<4} : {4:<4} : {5:<15} : {6:<45}'
    headers = [
        header for header in chain(Netgroup._fields, Member._fields)
        if not header == 'member']
    print(template.format(*headers))

    for row in report_rows:
        print(template.format(
            row.groupname,
            row.grp,
            row.env,
            row.role,
            row.keep,
            row.member.userid,
            row.member.fullname
            ))
