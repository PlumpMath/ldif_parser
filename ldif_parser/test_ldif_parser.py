#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Test suite for ldif_parser module
"""

import unittest
from random import sample, randrange
from pprint import pprint
from utils import coroutine, clean

import ldif_parser

MOCK_DATA_FILE = 'mock-data.txt'

def mock_get_data(fname):
    """return an iterator to data held in mocks file"""
    from os.path import dirname, join
    input_file = join(dirname(__file__), fname)
    return (line for line in open(input_file, 'r'))

@coroutine
def mock_get_fullname():
    """Generate fake full names for mock data"""
    import string
    source = '   '.join((string.lowercase, string.uppercase))
    while True:
        userlist, userid = (yield)
        userlist.append(ldif_parser.Member(userid, ''.join(sample(source, randrange(15, 46)))))

class LdifTests(unittest.TestCase):
    """Unit tests of ldif to tuple function"""

    def test_ldif_to_tuple(self):
        """Test ldif line to tuple"""
        test_ldif = 'sn: Dürer'
        self.assertEquals(
            ldif_parser.ldif_to_tuple(test_ldif),
            ('sn', 'Dürer'),
            msg="ldif_to_tuple does not match expected result ('sn', 'Dürer')")

    def test_ldif_to_tuple_no_partition(self):
        """Test incorrectly formatted ldif line to tuple"""
        test_ldif = 'sn Dürer'
        self.assertRaises(
            ldif_parser.InvalidLdifError,
            ldif_parser.ldif_to_tuple, test_ldif)

    def test_ldif_to_tuple_invalid_type(self):
        """Test incorrect type being passed to ldif_to_tuple"""
        test_ldif = 3
        self.assertRaises(
            AttributeError,
            ldif_parser.ldif_to_tuple, test_ldif)

class CompileReportTests(unittest.TestCase):
    """Unit test of compile report function"""

    def setUp(self):
        """Monkey patch to bypass using the 'ldaplist' command"""
        # monkey patch data source and bypass initial LDAP lookups
        ldif_parser.source = mock_get_data(MOCK_DATA_FILE)
        # monkey patch the get_fullname co-routine
        # to bypass secondary LDAP lookups
        ldif_parser.get_fullname = mock_get_fullname

    def tearDown(self):
        """Cleanup"""
        print('')
        pprint(self.test_report)
        print('')

    def test_compile_report(self):
        """Run the report with the mock data"""
        self.test_report = list()
        report_builder = ldif_parser.compile_report()
        for line in ldif_parser.clean(ldif_parser.source):
            report_builder.send((self.test_report, line))
        report_builder.send((self.test_report, ''))
        self.assertTrue(
            self.test_report,
            msg='Length of report is {0}'.format(len(self.test_report)))

def build_suite():
    """Build the test suite"""
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(LdifTests, 'test'))
    suite.addTest(unittest.makeSuite(CompileReportTests, 'test'))
    return suite

if __name__ == '__main__':
    test_suite = build_suite()
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(test_suite)
