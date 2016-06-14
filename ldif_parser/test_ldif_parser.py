#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import unittest
from random import sample, randrange

import ldif_parser

MOCK_DATA_FILE = 'mock-data.txt'

def mock_get_data(fname):
    """return an iterator to data held in mocks file"""
    from os.path import dirname, join
    input_file = join(dirname(__file__), fname)
    return (line for line in open(input_file, 'r'))

@ldif_parser.coroutine
def mock_get_fullname():
    """Generate fake full names for mock data"""
    import string
    source = '   '.join((string.lowercase, string.uppercase))
    while True:
        userlist, userid = (yield)
        userlist.append(ldif_parser.Member(userid, ''.join(sample(source, randrange(15, 46)))))

class LdifTests(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_ldif_to_tuple(self):
        test_ldif = 'sn: Dürer'
        self.assertEquals(
            ldif_parser.ldif_to_tuple(test_ldif),
            ('sn', 'Dürer'),
            msg="ldif_to_tuple does not match expected result ('sn', 'Dürer')")

    def test_ldif_to_tuple_no_partition(self):
        test_ldif = 'sn Dürer'
        self.assertRaises(
            ldif_parser.InvalidLdifError,
            ldif_parser.ldif_to_tuple, test_ldif)

    def test_ldif_to_tuple_invalid_type(self):
        test_ldif = 3
        self.assertRaises(
            AttributeError,
            ldif_parser.ldif_to_tuple, test_ldif)

    def test_compile_report(self):
        from pprint import pprint
        # monkey patch data source and bypass initial LDAP lookups
        ldif_parser.source = mock_get_data(MOCK_DATA_FILE)
        # monkey patch the get_fullname co-routine
        # to bypass secondary LDAP lookups
        ldif_parser.get_fullname = mock_get_fullname

        report = list()
        report_builder = ldif_parser.compile_report()
        for line in ldif_parser.clean(ldif_parser.source):
            report_builder.send((report, line))
        report_builder.send((report, ''))
        self.assertTrue(report, msg='Length of report is {0}'.format(len(report)))

if __name__ == '__main__':
    unittest.main()
