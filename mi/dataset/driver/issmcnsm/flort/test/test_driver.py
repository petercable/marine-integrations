"""
@package mi.dataset.driver.issmcnsm.flort.test.test_driver
@file marine-integrations/mi/dataset/driver/issmcnsm/flort/driver.py
@author Emily Hahn
@brief Test cases for issmcnsm_flort driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import unittest

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DataSourceConfigKey
from mi.dataset.dataset_driver import DriverParameter

from pyon.agent.agent import ResourceAgentState

from mi.dataset.driver.issmcnsm.flort.driver import IssmCnsmFLORTDDataSetDriver
from mi.dataset.parser.issmcnsm_flortd import Issmcnsm_flortdParserDataParticle

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.issmcnsm.flort.driver',
    driver_class='IssmCnsmFLORTDDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = IssmCnsmFLORTDDataSetDriver.stream_config(),
    startup_config = {
        'harvester':
        {
            'directory': '/tmp/dsatest',
            'pattern': '*.flort.log',
            'frequency': 1,
        },
        'parser': {}
    }
)

SAMPLE_STREAM = 'issmcnsm_flortd_parsed'

###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):
 
    def test_get(self):
        """
        Test that we can get data from files.  Verify that the driver
        sampling can be started and stopped
        """
        self.clear_sample_data()

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('test_data_1.flort.log', "20130101.flort.log")
        self.assert_data(Issmcnsm_flortdParserDataParticle, 'test_data_1.txt.result.yml', count=2, timeout=10)

        self.clear_async_data()
        self.create_sample_data('test_data_2.flort.log', "20130102.flort.log")
        self.assert_data(Issmcnsm_flortdParserDataParticle, 'test_data_2.txt.result.yml', count=4, timeout=10)

        self.clear_async_data()
        # skipping a file index 20130103 here to make sure it still finds the new file
        self.create_sample_data('test_data_3.flort.log', "20130104.flort.log")
        self.assert_data(Issmcnsm_flortdParserDataParticle, count=15, timeout=30)

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('test_data_1.flort.log', "20130105.flort.log")
        self.assert_data(Issmcnsm_flortdParserDataParticle, count=2, timeout=10)

    def test_resume_file_start(self):
        """
        Test the ability to restart the process
        """
        # Create and store the new driver state, after completed reading 20130101.dosta.log
        self.memento = {DataSourceConfigKey.HARVESTER: '/tmp/dsatest/20130101.flort.log',
                        DataSourceConfigKey.PARSER: None}
        self.driver = IssmCnsmFLORTDDataSetDriver(
            self._driver_config()['startup_config'],
            self.memento,
            self.data_callback,
            self.state_callback,
            self.exception_callback)

        # create some data to parse
        self.clear_async_data()
        self.create_sample_data('test_data_1.flort.log', "20130101.flort.log")
        self.create_sample_data('test_data_2.flort.log', "20130102.flort.log")

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(Issmcnsm_flortdParserDataParticle, 'test_data_2.txt.result.yml', count=4, timeout=10)

    def test_resume_mid_file(self):
        """
        Test the ability to restart the process in the middle of a file
        """
        # Create and store the new driver state, after completed reading  20130101.dosta.log
        self.memento = {DataSourceConfigKey.HARVESTER: '/tmp/dsatest/20130101.flort.log',
                        DataSourceConfigKey.PARSER: {'position': 146, 'timestamp': 3592854648.401}}
        self.driver = IssmCnsmFLORTDDataSetDriver(
            self._driver_config()['startup_config'],
            self.memento,
            self.data_callback,
            self.state_callback,
            self.exception_callback)

        # create some data to parse
        self.clear_async_data()
        self.create_sample_data('test_data_1.flort.log', "20130101.flort.log")
        self.create_sample_data('test_data_2.flort.log', "20130102.flort.log")

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(Issmcnsm_flortdParserDataParticle, 'test_data_2.txt.partial-result.yml', count=2, timeout=10)

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):
    def setUp(self):
        super(QualificationTest, self).setUp()

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.create_sample_data('test_data_1.flort.log', "20130101.flort.log")
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Right now, there is an issue with keeping records in order,
        # which has to do with the sleep time in get_samples in
        # instrument_agent_client.  By setting this delay more than the
        # delay in get_samples, the records are returned in the expected
        # otherwise they are returned out of order
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(SAMPLE_STREAM, 2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data('test_data_3.flort.log', "20130103.flort.log")
        self.assert_initialize()

        result = self.get_samples(SAMPLE_STREAM,15,30)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data('test_data_1.flort.log', "20130101.flort.log")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.get_samples(SAMPLE_STREAM, 2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            self.create_sample_data('test_data_2.flort.log', "20130102.flort.log")
            # Now read the first records of the second file then stop
            result = self.get_samples(SAMPLE_STREAM, 2)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            # Restart sampling and ensure we get the last 3 records of the file
            self.assert_start_sampling()
            result = self.get_samples(SAMPLE_STREAM, 2)
            self.assert_data_values(result, 'test_data_2.txt.partial-result.yml')

            self.assert_sample_queue_size(SAMPLE_STREAM, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")


