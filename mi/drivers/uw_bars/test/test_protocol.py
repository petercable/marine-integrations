#!/usr/bin/env python

__author__ = "Carlos Rueda"
__license__ = 'Apache 2.0'


from mi.drivers.uw_bars.test.pyon_test import PyonBarsTestCase
"""
from mi.drivers.uw_bars.protocol import BarsInstrumentProtocol
from mi.drivers.uw_bars.protocol import BarsProtocolState
"""
import time

from nose.plugins.attrib import attr
import unittest

@attr('UNIT', group='mi')
@unittest.skip('Need to align.')
class ProtocolTest(PyonBarsTestCase):

    def test(self):
        """
        BARS protocol tests
        """

        protocol = BarsInstrumentProtocol()
        self.assertEqual(BarsProtocolState.PRE_INIT,
                         protocol.get_current_state())

        protocol.initialize()
        protocol.configure(self.config)
        protocol.connect()

        self.assertEqual(BarsProtocolState.COLLECTING_DATA,
                         protocol.get_current_state())

        print "sleeping for a bit"
        time.sleep(5)

        print "disconnecting"
        protocol.disconnect()