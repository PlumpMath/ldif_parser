#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
This module parses data extracted from a large corporate
LDAP directory in LDIF format using the Linux 'ldaplist' command.
The module is designed to analyse LDAP group names and
use this information to produce a CSV report of all group members
annotated with metadata derived from a standard naming convention
used for the group name. The module was written to be run on a host
restricted to using python 2.6.

The module attempts to solve this problem in a functional
programming style using generators and coroutines. The generators
and coroutines are chained together to create a parsing pipeline
that analyses and manipulates each item of data as it is retrieved
by the 'ldaplist' command.

    get_group_data -> compile_report -> get_username -> get_fullname

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
from utils import varargs, coroutine, clean

# NamedTuples

Netgroup = namedtuple('Netgroup', ['groupname', 'grp', 'env', 'role', 'member', 'keep'])
Member = namedtuple('Member', ['userid', 'fullname'])

class Error(Exception):
    """Default custom exception"""

class InvalidLdifError(Error):
    """Raise this custom exception for incorrectly formatted LDIF lines"""
    def __init__(self):
        Exception.__init__(self, 'Received invalid LDIF data')

def get_group_data(netgroups):
    """Call 'ldaplist' to retrieve LDIF-formatted data from LDAP"""
    cmd = shlex.split('ldaplist -l netgroup {0}'.format(' '.join(netgroups)))
    results = Popen(cmd, stdout=PIPE).communicate()[0].splitlines()
    for line in results:
        yield line

def ldif_to_tuple(ldif):
    """Convert LDAP data to tuple

    Split a LDIF line into a tuple"""
    attr, colon, value = ldif.partition(':')
    if not colon:
        raise InvalidLdifError
    return tuple((attr.strip(), value.strip()))

@coroutine
def get_fullname():
    """Lookup fullnames from ldap

    Cache the results in a local dict to speed up subsequent lookups"""
    cache = dict()
    fullname_attrs = set(['displayName', 'description', 'gecos'])
    while True:
        userlist, userid = (yield)
        try:
            fullname = cache[userid]
        except KeyError: # not found in cache so lookup user in LDAP
            cmd = shlex.split(r'ldaplist -l passwd {userid}'.format(userid=userid))
            user_record = Popen(cmd, stdout=PIPE).communicate()[0].splitlines()
            user_detail_tuples = imap(ldif_to_tuple, user_record)
            user_names = (
                value for attr, value in user_detail_tuples
                if attr in fullname_attrs)
            fullname = max(user_names, key=len)
            cache[userid] = fullname
            userlist.append(Member(userid, fullname))

@coroutine
def get_username():
    """Get username from nisNetgroupTriple

    Regex pattern to extract the username from a nisNetgroupTriple"""
    username_pattern = re.compile(r',(?P<user>[a-zA-Z0-9]+),')
    find_fullname = get_fullname()
    while True:
        userlist, line = (yield)
        matches = username_pattern.search(line)
        if matches:
            find_fullname.send((userlist, matches.group('user')))

@coroutine
def compile_report():
    """Coroutine to process ldif stream"""
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

    source = get_group_data(options.grps)

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
