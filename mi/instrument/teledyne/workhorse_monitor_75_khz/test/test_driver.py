"""
@package mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.test.test_driver
@file marine-integrations/mi/instrument/teledyne/workhorse_monitor_75_khz/ooicore/driver.py
@author Roger Unwin
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import socket

import unittest
import time as time
import datetime as dt
from mi.core.time import get_timestamp_delayed

from nose.plugins.attrib import attr
from mock import Mock
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.log import get_logger; log = get_logger()

# MI imports.
from mi.idk.unit_test import AgentCapabilityType
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import DriverStartupConfigKey

from mi.instrument.teledyne.test.test_driver import TeledyneUnitTest
from mi.instrument.teledyne.test.test_driver import TeledyneIntegrationTest
from mi.instrument.teledyne.test.test_driver import TeledyneQualificationTest
from mi.instrument.teledyne.test.test_driver import TeledynePublicationTest

from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import InstrumentDriver
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import DataParticleType
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import InstrumentCmds
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ProtocolState
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ProtocolEvent
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import Capability
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import Parameter
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import Protocol

from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ScheduledJob
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import Prompt
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import NEWLINE

from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_PD0_PARSED_KEY
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_PD0_PARSED_DataParticle
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_SYSTEM_CONFIGURATION_KEY
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_SYSTEM_CONFIGURATION_DataParticle
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_COMPASS_CALIBRATION_KEY
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_COMPASS_CALIBRATION_DataParticle

from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import SAMPLE_RAW_DATA 
from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import CALIBRATION_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import PS0_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import PS3_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import FD_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import PT200_RAW_DATA

from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentCommandException
from pyon.core.exception import Conflict
from pyon.agent.agent import ResourceAgentEvent

from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import ResourceAgentState
from random import randint

from mi.idk.unit_test import AGENT_DISCOVER_TIMEOUT
from mi.idk.unit_test import GO_ACTIVE_TIMEOUT
from mi.idk.unit_test import GET_TIMEOUT
from mi.idk.unit_test import SET_TIMEOUT
from mi.idk.unit_test import EXECUTE_TIMEOUT

AGENT_DISCOVER_TIMEOUT=3600
GO_ACTIVE_TIMEOUT=3600 # i have a slow instrument
GET_TIMEOUT=3000
SET_TIMEOUT=9000
EXECUTE_TIMEOUT=3000

tolerance = 500

# Globals
raw_stream_received = False
parsed_stream_received = False






#################################### RULES ####################################
#                                                                             #
# Common capabilities in the base class                                       #
#                                                                             #
# Instrument specific stuff in the derived class                              #
#                                                                             #
# Generator spits out either stubs or comments describing test this here,     #
# test that there.                                                            #
#                                                                             #
# Qualification tests are driven through the instrument_agent                 #
#                                                                             #
###############################################################################

###
#   Driver constant definitions
###

###############################################################################
#                           DATA PARTICLE TEST MIXIN                          #
#     Defines a set of assert methods used for data particle verification     #
#                                                                             #
#  In python mixin classes are classes designed such that they wouldn't be    #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.
###############################################################################


class ADCPTMixin(DriverTestMixin):
    '''
    Mixin class used for storing data particle constance
    and common data assertion methods.
    '''
    # Create some short names for the parameter test config
    TYPE      = ParameterTestConfigKey.TYPE
    READONLY  = ParameterTestConfigKey.READONLY
    STARTUP   = ParameterTestConfigKey.STARTUP
    DA        = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE     = ParameterTestConfigKey.VALUE
    REQUIRED  = ParameterTestConfigKey.REQUIRED
    DEFAULT   = ParameterTestConfigKey.DEFAULT
    STATES    = ParameterTestConfigKey.STATES 
    
    ###
    # Parameter and Type Definitions
    ###
    # Is DEFAULT the DEFAULT STARTUP VALUE?
    _driver_parameters = {
        Parameter.SERIAL_DATA_OUT: {TYPE: str, READONLY: True, DA: False, STARTUP: False, DEFAULT: False},
        Parameter.SERIAL_FLOW_CONTROL: {TYPE: str, READONLY: True, DA: False, STARTUP: True, DEFAULT: False, VALUE: '11110'},
        Parameter.SAVE_NVRAM_TO_RECORDER: {TYPE: bool, READONLY: True, DA: False, STARTUP: True, DEFAULT: True, VALUE: True},
        Parameter.TIME: {TYPE: str, READONLY: True, DA: False, STARTUP: False, DEFAULT: False},
        Parameter.SERIAL_OUT_FW_SWITCHES: {TYPE: str, READONLY: True, DA: False, STARTUP: True, DEFAULT: False, VALUE: '111100000'},
        Parameter.WATER_PROFILING_MODE: {TYPE: int, READONLY: True, DA: False, STARTUP: True, DEFAULT: False, VALUE: 1},

        Parameter.BANNER: {TYPE: bool, READONLY: True, DA: False, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.INSTRUMENT_ID: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.SLEEP_ENABLE: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.POLLED_MODE: {TYPE: bool, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.XMIT_POWER: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 255, VALUE: 255},
        Parameter.SPEED_OF_SOUND: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 1485, VALUE: 1485},
        Parameter.PITCH: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.ROLL: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.SALINITY: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 35, VALUE: 35},
        Parameter.COORDINATE_TRANSFORMATION: {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '00111', VALUE: '00111'},
        Parameter.SENSOR_SOURCE: {TYPE: str, READONLY: False, DA: False, STARTUP: False, DEFAULT: False, VALUE: "1111101"},
        Parameter.TIME_PER_ENSEMBLE: {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: '00:00:00.00'},
        Parameter.TIME_OF_FIRST_PING: {TYPE: str, READONLY: False, DA: False, STARTUP: False, DEFAULT: False}, # STARTUP: True, VALUE: '****/**/**,**:**:**'
        Parameter.TIME_PER_PING: {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: '00:01.00'},
        Parameter.FALSE_TARGET_THRESHOLD: {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: '050,001'},
        Parameter.BANDWIDTH_CONTROL: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 0},
        Parameter.CORRELATION_THRESHOLD: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 64},
        Parameter.ERROR_VELOCITY_THRESHOLD: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 2000},
        Parameter.BLANK_AFTER_TRANSMIT: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 704},
        Parameter.CLIP_DATA_PAST_BOTTOM: {TYPE: bool, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 0},
        Parameter.RECEIVER_GAIN_SELECT: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 1},
        Parameter.WATER_REFERENCE_LAYER: {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: '001,005'},
        Parameter.NUMBER_OF_DEPTH_CELLS: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 100},
        Parameter.PINGS_PER_ENSEMBLE: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 1},
        Parameter.DEPTH_CELL_SIZE: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 800},
        Parameter.TRANSMIT_LENGTH: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 0},
        Parameter.PING_WEIGHT: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 0},
        Parameter.AMBIGUITY_VELOCITY: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 175}
    }

    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.START_AUTOSAMPLE: { STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.STOP_AUTOSAMPLE: { STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.CLOCK_SYNC: { STATES: [ProtocolState.COMMAND]},
        Capability.GET_CALIBRATION: { STATES: [ProtocolState.COMMAND]},
        Capability.GET_CONFIGURATION: { STATES: [ProtocolState.COMMAND]},
        Capability.SAVE_SETUP_TO_RAM: { STATES: [ProtocolState.COMMAND]},
        Capability.SEND_LAST_SAMPLE: { STATES: [ProtocolState.COMMAND]},
        Capability.GET_ERROR_STATUS_WORD: { STATES: [ProtocolState.COMMAND]},
        Capability.CLEAR_ERROR_STATUS_WORD: { STATES: [ProtocolState.COMMAND]},
        Capability.GET_FAULT_LOG: { STATES: [ProtocolState.COMMAND]},
        Capability.CLEAR_FAULT_LOG: { STATES: [ProtocolState.COMMAND]},
        Capability.GET_INSTRUMENT_TRANSFORM_MATRIX: { STATES: [ProtocolState.COMMAND]},
        Capability.RUN_TEST_200: { STATES: [ProtocolState.COMMAND]},
    }

    #name, type done, value pending
    EF_CHAR = '\xef'
    _calibration_data_parameters = {
        ADCP_COMPASS_CALIBRATION_KEY.FLUXGATE_CALIBRATION_TIMESTAMP: {'type': float, 'value': 1347639932.0 },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_BX: {'type': list, 'value': [0.39218, 0.3966, -0.031681, 0.0064332] },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_BY: {'type': list, 'value': [-0.02432, -0.010376, -0.0022428, -0.60628] },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_BZ: {'type': list, 'value': [0.22453, -0.21972, -0.2799, -0.0024339] },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_ERR: {'type': list, 'value': [0.46514, -0.40455, 0.69083, -0.014291] },
        ADCP_COMPASS_CALIBRATION_KEY.COIL_OFFSET: {'type': list, 'value': [34233.0, 34449.0, 34389.0, 34698.0] },
        ADCP_COMPASS_CALIBRATION_KEY.ELECTRICAL_NULL: {'type': float, 'value': 34285.0 },
        ADCP_COMPASS_CALIBRATION_KEY.TILT_CALIBRATION_TIMESTAMP: {'type': float, 'value': 1347639285.0 },
        ADCP_COMPASS_CALIBRATION_KEY.CALIBRATION_TEMP: {'type': float, 'value': 24.4 },
        ADCP_COMPASS_CALIBRATION_KEY.ROLL_UP_DOWN: {'type': list, 'value': [7.4612e-07, -3.1727e-05, -3.0054e-07, 3.219e-05] },
        ADCP_COMPASS_CALIBRATION_KEY.PITCH_UP_DOWN: {'type': list, 'value': [-3.1639e-05, -6.3505e-07, -3.1965e-05, -1.4881e-07] },
        ADCP_COMPASS_CALIBRATION_KEY.OFFSET_UP_DOWN: {'type': list, 'value': [32808.0, 32568.0, 32279.0, 33047.0] },
        ADCP_COMPASS_CALIBRATION_KEY.TILT_NULL: {'type': float, 'value': 33500.0 }
    }

    #name, type done, value pending
    _system_configuration_data_parameters = {
        ADCP_SYSTEM_CONFIGURATION_KEY.SERIAL_NUMBER: {'type': unicode, 'value': "18444" },
        ADCP_SYSTEM_CONFIGURATION_KEY.TRANSDUCER_FREQUENCY: {'type': int, 'value': 76800 }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.CONFIGURATION: {'type': unicode, 'value': "4 BEAM, JANUS" },
        ADCP_SYSTEM_CONFIGURATION_KEY.MATCH_LAYER: {'type': unicode, 'value': "10" },
        ADCP_SYSTEM_CONFIGURATION_KEY.BEAM_ANGLE: {'type': int, 'value': 20 },
        ADCP_SYSTEM_CONFIGURATION_KEY.BEAM_PATTERN: {'type': unicode, 'value': "CONVEX" },
        ADCP_SYSTEM_CONFIGURATION_KEY.ORIENTATION: {'type': unicode, 'value': "UP" },
        ADCP_SYSTEM_CONFIGURATION_KEY.SENSORS: {'type': unicode, 'value': "HEADING  TILT 1  TILT 2  DEPTH  TEMPERATURE  PRESSURE" },
        ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_c3: {'type': float, 'value': -1.927850E-11 },
        ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_c2: {'type': float, 'value': +1.281892E-06 },
        ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_c1: {'type': float, 'value': +1.375793E+00 },
        ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_OFFSET: {'type': float, 'value': 13.38634 },
        ADCP_SYSTEM_CONFIGURATION_KEY.TEMPERATURE_SENSOR_OFFSET: {'type': float, 'value': -0.01 },
        ADCP_SYSTEM_CONFIGURATION_KEY.CPU_FIRMWARE: {'type': unicode, 'value': "50.40 [0]" },
        ADCP_SYSTEM_CONFIGURATION_KEY.BOOT_CODE_REQUIRED: {'type': unicode, 'value': "1.16" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.BOOT_CODE_ACTUAL: {'type': unicode, 'value': "1.16" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_1_VERSION: {'type': unicode, 'value': "ad48" },
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_1_TYPE: {'type': unicode, 'value': "1f" },
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_2_VERSION: {'type': unicode, 'value': "ad48" },
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_2_TYPE: {'type': unicode, 'value': "1f" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.POWER_TIMING_VERSION: {'type': unicode, 'value': "85d3" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.POWER_TIMING_TYPE: {'type': unicode, 'value': "7" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS: {'type': unicode, 'value': u"72  00 00 06 FE BC D8  09 HPA727-3009-00B \n" + \
                                                                                    "81  00 00 06 F5 CD 9E  09 REC727-1004-06A\n" + \
                                                                                    "A5  00 00 06 FF 1C 79  09 HPI727-3007-00A\n" + \
                                                                                    "82  00 00 06 FF 23 E5  09 CPU727-2011-00E\n" + \
                                                                                    "07  00 00 06 F6 05 15  09 TUN727-1005-06A\n" + \
                                                                                    "DB  00 00 06 F5 CB 5D  09 DSP727-2001-06H" }
    }

    #name, type done, value pending
    _pd0_parameters_base = {
        ADCP_PD0_PARSED_KEY.HEADER_ID: {'type': int, 'value': 127 },
        ADCP_PD0_PARSED_KEY.DATA_SOURCE_ID: {'type': int, 'value': 127 },
        ADCP_PD0_PARSED_KEY.NUM_BYTES: {'type': int, 'value': 26632 },
        ADCP_PD0_PARSED_KEY.NUM_DATA_TYPES: {'type': int, 'value': 6 },
        ADCP_PD0_PARSED_KEY.OFFSET_DATA_TYPES: {'type': list, 'value': [18, 77, 142, 944, 1346, 1748, 2150] },
        ADCP_PD0_PARSED_KEY.FIXED_LEADER_ID: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.FIRMWARE_VERSION: {'type': int, 'value': 50 },
        ADCP_PD0_PARSED_KEY.FIRMWARE_REVISION: {'type': int, 'value': 40 },
        ADCP_PD0_PARSED_KEY.SYSCONFIG_FREQUENCY: {'type': int, 'value': 150 },
        ADCP_PD0_PARSED_KEY.SYSCONFIG_BEAM_PATTERN: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.SYSCONFIG_SENSOR_CONFIG: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SYSCONFIG_HEAD_ATTACHED: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SYSCONFIG_VERTICAL_ORIENTATION: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.DATA_FLAG: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.LAG_LENGTH: {'type': int, 'value': 53 },
        ADCP_PD0_PARSED_KEY.NUM_BEAMS: {'type': int, 'value': 4 },
        ADCP_PD0_PARSED_KEY.NUM_CELLS: {'type': int, 'value': 100 },
        ADCP_PD0_PARSED_KEY.PINGS_PER_ENSEMBLE: {'type': int, 'value': 256 },
        ADCP_PD0_PARSED_KEY.DEPTH_CELL_LENGTH: {'type': int, 'value': 32780 },
        ADCP_PD0_PARSED_KEY.BLANK_AFTER_TRANSMIT: {'type': int, 'value': 49154 },
        ADCP_PD0_PARSED_KEY.SIGNAL_PROCESSING_MODE: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.LOW_CORR_THRESHOLD: {'type': int, 'value': 64 },
        ADCP_PD0_PARSED_KEY.NUM_CODE_REPETITIONS: {'type': int, 'value': 17 },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_MIN: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.ERROR_VEL_THRESHOLD: {'type': int, 'value': 53255 },
        ADCP_PD0_PARSED_KEY.TIME_PER_PING_MINUTES: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.TIME_PER_PING_SECONDS: {'type': float, 'value': 1.0 },
        ADCP_PD0_PARSED_KEY.COORD_TRANSFORM_TYPE: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.COORD_TRANSFORM_TILTS: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.COORD_TRANSFORM_BEAMS: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.COORD_TRANSFORM_MAPPING: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.HEADING_ALIGNMENT: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.HEADING_BIAS: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_SPEED: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_DEPTH: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_HEADING: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_PITCH: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_ROLL: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_CONDUCTIVITY: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_TEMPERATURE: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_AVAILABLE_DEPTH: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_AVAILABLE_HEADING: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_AVAILABLE_PITCH: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_AVAILABLE_ROLL: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_AVAILABLE_CONDUCTIVITY: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.SENSOR_AVAILABLE_TEMPERATURE: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.BIN_1_DISTANCE: {'type': int, 'value': 60175 },
        ADCP_PD0_PARSED_KEY.TRANSMIT_PULSE_LENGTH: {'type': int, 'value': 4109 },
        ADCP_PD0_PARSED_KEY.REFERENCE_LAYER_START: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.REFERENCE_LAYER_STOP: {'type': int, 'value': 5 },
        ADCP_PD0_PARSED_KEY.FALSE_TARGET_THRESHOLD: {'type': int, 'value': 50 },
        ADCP_PD0_PARSED_KEY.LOW_LATENCY_TRIGGER: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.TRANSMIT_LAG_DISTANCE: {'type': int, 'value': 50688 },
        ADCP_PD0_PARSED_KEY.CPU_BOARD_SERIAL_NUMBER: {'type': long, 'value': 9367487254980977929L },
        ADCP_PD0_PARSED_KEY.SYSTEM_BANDWIDTH: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.SYSTEM_POWER: {'type': int, 'value': 255 },
        ADCP_PD0_PARSED_KEY.SERIAL_NUMBER: {'type': int, 'value': 206045184 },
        ADCP_PD0_PARSED_KEY.BEAM_ANGLE: {'type': int, 'value': 20 },
        ADCP_PD0_PARSED_KEY.VARIABLE_LEADER_ID: {'type': int, 'value': 128 },
        ADCP_PD0_PARSED_KEY.ENSEMBLE_NUMBER: {'type': int, 'value': 5 },
        ADCP_PD0_PARSED_KEY.INTERNAL_TIMESTAMP: {'type': float, 'value': 752 },
        ADCP_PD0_PARSED_KEY.ENSEMBLE_NUMBER_INCREMENT: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.BIT_RESULT_DEMOD_1: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.BIT_RESULT_DEMOD_2: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.BIT_RESULT_TIMING: {'type': int, 'value': 0  },
        ADCP_PD0_PARSED_KEY.SPEED_OF_SOUND: {'type': int, 'value': 1523 },
        ADCP_PD0_PARSED_KEY.TRANSDUCER_DEPTH: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.HEADING: {'type': int, 'value': 5221 },
        ADCP_PD0_PARSED_KEY.PITCH: {'type': int, 'value': -4657 },
        ADCP_PD0_PARSED_KEY.ROLL: {'type': int, 'value': -4561 },
        ADCP_PD0_PARSED_KEY.SALINITY: {'type': int, 'value': 35 },
        ADCP_PD0_PARSED_KEY.TEMPERATURE: {'type': int, 'value': 2050     },
        ADCP_PD0_PARSED_KEY.MPT_MINUTES: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.MPT_SECONDS: {'type': float, 'value': 0.0 },
        ADCP_PD0_PARSED_KEY.HEADING_STDEV: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.PITCH_STDEV: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.ROLL_STDEV: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.ADC_TRANSMIT_CURRENT: {'type': int, 'value': 116 },
        ADCP_PD0_PARSED_KEY.ADC_TRANSMIT_VOLTAGE: {'type': int, 'value': 169 },
        ADCP_PD0_PARSED_KEY.ADC_AMBIENT_TEMP: {'type': int, 'value': 88 },
        ADCP_PD0_PARSED_KEY.ADC_PRESSURE_PLUS: {'type': int, 'value': 79 },
        ADCP_PD0_PARSED_KEY.ADC_PRESSURE_MINUS: {'type': int, 'value': 79 },
        ADCP_PD0_PARSED_KEY.ADC_ATTITUDE_TEMP: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.ADC_ATTITUDE: {'type': int, 'value': 0   },
        ADCP_PD0_PARSED_KEY.ADC_CONTAMINATION_SENSOR: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.BUS_ERROR_EXCEPTION: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.ADDRESS_ERROR_EXCEPTION: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.ILLEGAL_INSTRUCTION_EXCEPTION: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.ZERO_DIVIDE_INSTRUCTION: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.EMULATOR_EXCEPTION: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.UNASSIGNED_EXCEPTION: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.WATCHDOG_RESTART_OCCURED: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.BATTERY_SAVER_POWER: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.PINGING: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.COLD_WAKEUP_OCCURED: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.UNKNOWN_WAKEUP_OCCURED: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.CLOCK_READ_ERROR: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.UNEXPECTED_ALARM: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.CLOCK_JUMP_FORWARD: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.CLOCK_JUMP_BACKWARD: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.POWER_FAIL: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.SPURIOUS_DSP_INTERRUPT: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.SPURIOUS_UART_INTERRUPT: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.SPURIOUS_CLOCK_INTERRUPT: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.LEVEL_7_INTERRUPT: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.ABSOLUTE_PRESSURE: {'type': int, 'value': 4294963793 },
        ADCP_PD0_PARSED_KEY.PRESSURE_VARIANCE: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.INTERNAL_TIMESTAMP: {'type': float, 'value': 1363408382.02 },
        ADCP_PD0_PARSED_KEY.VELOCITY_DATA_ID: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_ID: {'type': int, 'value': 2 },
        ADCP_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_BEAM1: {'type': list, 'value': [19801, 1796, 1800, 1797, 1288, 1539, 1290, 1543, 1028, 1797, 1538, 775, 1034, 1283, 1029, 1799, 1801, 1545, 519, 772, 519, 1033, 1028, 1286, 521, 519, 1545, 1801, 522, 1286, 1030, 1032, 1542, 1035, 1283, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_BEAM2: {'type': list, 'value': [22365, 2057, 2825, 2825, 1801, 2058, 1545, 1286, 3079, 522, 1547, 519, 2052, 2820, 519, 1806, 1026, 1547, 1795, 1801, 2311, 1030, 781, 1796, 1037, 1802, 1035, 1798, 770, 2313, 1292, 1031, 1030, 2830, 523, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_BEAM3: {'type': list, 'value': [3853, 1796, 1289, 1803, 2317, 2571, 1028, 1282, 1799, 2825, 2574, 1026, 1028, 518, 1290, 1286, 1032, 1797, 1028, 2312, 1031, 775, 1549, 772, 1028, 772, 2570, 1288, 1796, 1542, 1538, 777, 1282, 773, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_BEAM4: {'type': list, 'value': [5386, 4100, 2822, 1286, 774, 1799, 518, 778, 3340, 1031, 1546, 1545, 1547, 2566, 3077, 3334, 1801, 1809, 2058, 1539, 1798, 1546, 3593, 1032, 2307, 1025, 1545, 2316, 2055, 1546, 1292, 2312, 1035, 2316, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.ECHO_INTENSITY_ID: {'type': int, 'value': 3 },
        ADCP_PD0_PARSED_KEY.ECHO_INTENSITY_BEAM1: {'type': list, 'value': [24925, 10538, 10281, 10537, 10282, 10281, 10281, 10282, 10282, 10281, 10281, 10281, 10538, 10282, 10281, 10282, 10281, 10537, 10281, 10281, 10281, 10281, 10281, 10281, 10281, 10281, 10281, 10281, 10281, 10282, 10281, 10282, 10537, 10281, 10281, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.ECHO_INTENSITY_BEAM2: {'type': list, 'value': [29027, 12334, 12334, 12078, 12078, 11821, 12334, 12334, 12078, 12078, 12078, 12078, 12078, 12078, 12078, 12079, 12334, 12078, 12334, 12333, 12078, 12333, 12078, 12077, 12078, 12078, 12078, 12334, 12077, 12078, 12078, 12078, 12078, 12078, 12078, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.ECHO_INTENSITY_BEAM3: {'type': list, 'value': [12079, 10282, 10281, 10281, 10282, 10281, 10282, 10282, 10281, 10025, 10282, 10282, 10282, 10282, 10025, 10282, 10281, 10025, 10281, 10281, 10282, 10281, 10282, 10281, 10281, 10281, 10537, 10282, 10281, 10281, 10281, 10281, 10281, 10282, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.ECHO_INTENSITY_BEAM4: {'type': list, 'value': [14387, 12334, 12078, 12078, 12078, 12334, 12078, 12334, 12078, 12078, 12077, 12077, 12334, 12078, 12334, 12078, 12334, 12077, 12078, 11821, 12335, 12077, 12078, 12077, 12334, 11822, 12334, 12334, 12077, 12077, 12078, 11821, 11821, 12078, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_ID: {'type': int, 'value': 4 },
        ADCP_PD0_PARSED_KEY.CHECKSUM: {'type': int, 'value': 8239 }
    }

    # red
    _coordinate_transformation_beam_parameters = {
        # Not yet defined
        ADCP_PD0_PARSED_KEY.WATER_VELOCITY_EAST: {'type': int, 'value': [] },
        ADCP_PD0_PARSED_KEY.WATER_VELOCITY_NORTH: {'type': int, 'value': [] },
        ADCP_PD0_PARSED_KEY.WATER_VELOCITY_UP: {'type': int, 'value': [] },
        ADCP_PD0_PARSED_KEY.ERROR_VELOCITY: {'type': int, 'value': [] },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_3BEAM: {'type': list, 'value': [] },
        ADCP_PD0_PARSED_KEY.PERCENT_TRANSFORMS_REJECT: {'type': list, 'value': [] },
        ADCP_PD0_PARSED_KEY.PERCENT_BAD_BEAMS: {'type': list, 'value': [] },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_4BEAM: {'type': list, 'value': [] },
        # empty place holders
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM1: {'type': list, 'value': [] },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM2: {'type': list, 'value': [] },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM3: {'type': list, 'value': [] },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM4: {'type': list, 'value': [] },
        ADCP_PD0_PARSED_KEY.BEAM_1_VELOCITY: {'type': list, 'value': [] },
        ADCP_PD0_PARSED_KEY.BEAM_2_VELOCITY: {'type': list, 'value': [] },
        ADCP_PD0_PARSED_KEY.BEAM_3_VELOCITY: {'type': list, 'value': [] },
        ADCP_PD0_PARSED_KEY.BEAM_4_VELOCITY  : {'type': list, 'value': [] }
    }

    # blue
    _coordinate_transformation_earth_parameters = {
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM1: {'type': list, 'value': [25700, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM2: {'type': list, 'value': [25700, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM3: {'type': list, 'value': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM4: {'type': list, 'value': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.BEAM_1_VELOCITY: {'type': list, 'value': [4864, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128] },
        ADCP_PD0_PARSED_KEY.BEAM_2_VELOCITY: {'type': list, 'value': [62719, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128] },
        ADCP_PD0_PARSED_KEY.BEAM_3_VELOCITY: {'type': list, 'value': [45824, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128] },
        ADCP_PD0_PARSED_KEY.BEAM_4_VELOCITY  : {'type': list, 'value': [19712, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128] },
        # empty place holders
        ADCP_PD0_PARSED_KEY.WATER_VELOCITY_EAST: {'type': int, 'value': [] },
        ADCP_PD0_PARSED_KEY.WATER_VELOCITY_NORTH: {'type': int, 'value': [] },
        ADCP_PD0_PARSED_KEY.WATER_VELOCITY_UP: {'type': int, 'value': [] },
        ADCP_PD0_PARSED_KEY.ERROR_VELOCITY: {'type': int, 'value': [] },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_3BEAM: {'type': list, 'value': [] },
        ADCP_PD0_PARSED_KEY.PERCENT_TRANSFORMS_REJECT: {'type': list, 'value': [] },
        ADCP_PD0_PARSED_KEY.PERCENT_BAD_BEAMS: {'type': list, 'value': [] },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_4BEAM: {'type': list, 'value': [] }
    }

    _pd0_parameters = dict(_pd0_parameters_base.items() +
                           _coordinate_transformation_earth_parameters.items())
    # Driver Parameter Methods
    ###
    def assert_driver_parameters(self, current_parameters, verify_values = False):
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        log.debug("assert_driver_parameters current_parameters = " + str(current_parameters))
        self.assert_parameters(current_parameters, self._driver_parameters, verify_values)

    ###
    # Data Particle Parameters Methods
    ###
    def assert_sample_data_particle(self, data_particle):
        '''
        Verify a particle is a know particle to this driver and verify the particle is  correct
        @param data_particle: Data particle of unkown type produced by the driver
        '''

        if (isinstance(data_particle, DataParticleType.ADCP_PD0_PARSED)):
            self.assert_particle_pd0_data(data_particle)
        elif (isinstance(data_particle, DataParticleType.ADCP_SYSTEM_CONFIGURATION)):
            self.assert_particle_system_configuration(data_particle)
        elif (isinstance(data_particle, DataParticleType.ADCP_COMPASS_CALIBRATION)):
            self.assert_particle_compass_calibration(data_particle)
        else:
            log.error("Unknown Particle Detected: %s" % data_particle)
            self.assertFalse(True)

    def assert_particle_compass_calibration(self, data_particle, verify_values = True):
        '''
        Verify an adcpt calibration data particle
        @param data_particle: ADCPT_CalibrationDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        log.debug("in assert_particle_compass_calibration")
        log.debug("data_particle = " + repr(data_particle))
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_COMPASS_CALIBRATION)
        self.assert_data_particle_parameters(data_particle, self._calibration_data_parameters, verify_values)

    def assert_particle_system_configuration(self, data_particle, verify_values = True):
        '''
        Verify an adcpt fd data particle
        @param data_particle: ADCPT_FDDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_SYSTEM_CONFIGURATION)
        self.assert_data_particle_parameters(data_particle, self._system_configuration_data_parameters, verify_values)

    def assert_particle_pd0_data(self, data_particle, verify_values = True):
        '''
        Verify an adcpt ps0 data particle
        @param data_particle: ADCPT_PS0DataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_PD0_PARSED)
        self.assert_data_particle_parameters(data_particle, self._pd0_parameters) # , verify_values


###############################################################################
#                                UNIT TESTS                                   #
###############################################################################
@attr('UNIT', group='mi')
class WorkhorseDriverUnitTest(TeledyneUnitTest, ADCPTMixin):
    def setUp(self):
        TeledyneUnitTest.setUp(self)

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilites
        """

        self.assert_enum_has_no_duplicates(InstrumentCmds())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(ScheduledJob())
        # Test capabilites for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_driver_schema(self):
        """
        get the driver schema and verify it is configured properly
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_driver_schema(driver, self._driver_parameters, self._driver_capabilities)

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, SAMPLE_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_RAW_DATA, 32)
        self.assert_chunker_combined_sample(chunker, SAMPLE_RAW_DATA)

        self.assert_chunker_sample(chunker, PS0_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, PS0_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, PS0_RAW_DATA, 32)
        self.assert_chunker_combined_sample(chunker, PS0_RAW_DATA)

        self.assert_chunker_sample(chunker, CALIBRATION_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, CALIBRATION_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, CALIBRATION_RAW_DATA, 32)
        self.assert_chunker_combined_sample(chunker, CALIBRATION_RAW_DATA)


    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        # Start validating data particles

        self.assert_particle_published(driver, CALIBRATION_RAW_DATA, self.assert_particle_compass_calibration, True)
        self.assert_particle_published(driver, PS0_RAW_DATA, self.assert_particle_system_configuration, True)
        self.assert_particle_published(driver, SAMPLE_RAW_DATA, self.assert_particle_pd0_data, True)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        protocol = Protocol(Prompt, NEWLINE, my_event_callback)
        driver_capabilities = Capability().list()
        test_capabilities = Capability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(driver_capabilities, protocol._filter_capabilities(test_capabilities))

    def test_driver_parameters(self):
        """
        Verify the set of parameters known by the driver
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)

        expected_parameters = sorted(self._driver_parameters.keys())
        reported_parameters = sorted(driver.get_resource(Parameter.ALL))

        log.debug("*** Expected Parameters: %s" % expected_parameters)
        log.debug("*** Reported Parameters: %s" % reported_parameters)

        self.assertEqual(reported_parameters, expected_parameters)

        # Verify the parameter definitions
        self.assert_driver_parameter_definition(driver, self._driver_parameters)

    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """
        capabilities = {
            ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER'],
            ProtocolState.COMMAND: ['DRIVER_EVENT_CLOCK_SYNC',
                                    'DRIVER_EVENT_GET',
                                    'DRIVER_EVENT_SET',
                                    'DRIVER_EVENT_START_AUTOSAMPLE',
                                    'DRIVER_EVENT_START_DIRECT',
                                    'PROTOCOL_EVENT_CLEAR_ERROR_STATUS_WORD',
                                    'PROTOCOL_EVENT_CLEAR_FAULT_LOG',
                                    'PROTOCOL_EVENT_GET_CALIBRATION',
                                    'PROTOCOL_EVENT_GET_CONFIGURATION',
                                    'PROTOCOL_EVENT_GET_ERROR_STATUS_WORD',
                                    'PROTOCOL_EVENT_GET_FAULT_LOG',
                                    'PROTOCOL_EVENT_GET_INSTRUMENT_TRANSFORM_MATRIX',
                                    'PROTOCOL_EVENT_RUN_TEST_200',
                                    'PROTOCOL_EVENT_SAVE_SETUP_TO_RAM',
                                    'PROTOCOL_EVENT_SCHEDULED_CLOCK_SYNC',
                                    'PROTOCOL_EVENT_SEND_LAST_SAMPLE'],
            ProtocolState.AUTOSAMPLE: ['DRIVER_EVENT_STOP_AUTOSAMPLE',
                                    'DRIVER_EVENT_GET',
                                    'PROTOCOL_EVENT_GET_CALIBRATION',
                                    'PROTOCOL_EVENT_GET_CONFIGURATION',
                                    'PROTOCOL_EVENT_SCHEDULED_CLOCK_SYNC'],
            ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT', 'EXECUTE_DIRECT']
        }

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)


###############################################################################
#                            INTEGRATION TESTS                                #
###############################################################################
@attr('INT', group='mi')
class WorkhorseDriverIntegrationTest(TeledyneIntegrationTest, ADCPTMixin):
    def setUp(self):
        TeledyneIntegrationTest.setUp(self)

    ###
    #    Add instrument specific integration tests
    ###
    def test_parameters(self):
        """
        Test driver parameters and verify their type.  Startup parameters also verify the parameter
        value.  This test confirms that parameters are being read/converted properly and that
        the startup has been applied.
        """
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        log.debug("REPLY = " + str(reply))
        self.assert_driver_parameters(reply, True)

    def test_set(self):
        """
        Test all set commands. Verify all exception cases.
        """
        self.assert_initialize_driver()

        params = {
            Parameter.INSTRUMENT_ID: 0,
            Parameter.SLEEP_ENABLE: 0,
            Parameter.POLLED_MODE: False,
            Parameter.XMIT_POWER: 255,
            Parameter.SPEED_OF_SOUND: 1485,
            Parameter.PITCH: 0,
            Parameter.ROLL: 0,
            Parameter.SALINITY: 35,
            Parameter.SENSOR_SOURCE: "1111101",
            Parameter.TIME_PER_ENSEMBLE: '00:00:00.00',
            Parameter.TIME_PER_PING: '00:01.00',
            Parameter.FALSE_TARGET_THRESHOLD: '050,001',
            Parameter.BANDWIDTH_CONTROL: 0,
            Parameter.CORRELATION_THRESHOLD: 64,
            Parameter.ERROR_VELOCITY_THRESHOLD: 2000,
            Parameter.BLANK_AFTER_TRANSMIT: 704,
            Parameter.CLIP_DATA_PAST_BOTTOM: False,
            Parameter.RECEIVER_GAIN_SELECT: 1,
            Parameter.WATER_REFERENCE_LAYER: '001,005',
            Parameter.NUMBER_OF_DEPTH_CELLS: 100,
            Parameter.PINGS_PER_ENSEMBLE: 1,
            Parameter.DEPTH_CELL_SIZE: 800,
            Parameter.TRANSMIT_LENGTH: 0,
            Parameter.PING_WEIGHT: 0,
            Parameter.AMBIGUITY_VELOCITY: 175,
        }

        # Set all parameters to a known ground state
        self.assert_set_bulk(params)

        ###
        #   Instrument Parameteres
        ###

        self.assert_set_readonly(Parameter.SERIAL_DATA_OUT)
        self.assert_set_readonly(Parameter.SERIAL_FLOW_CONTROL)
        self.assert_set_readonly(Parameter.SAVE_NVRAM_TO_RECORDER)
        self.assert_set_readonly(Parameter.WATER_PROFILING_MODE)
        self.assert_set_readonly(Parameter.SERIAL_OUT_FW_SWITCHES)
        self.assert_set_readonly(Parameter.BANNER)

        self.assert_set(Parameter.CORRELATION_THRESHOLD, 64)
        self.assert_set(Parameter.TIME_PER_ENSEMBLE, '00:00:00.00')
        self.assert_set(Parameter.INSTRUMENT_ID, 0)
        self.assert_set(Parameter.SLEEP_ENABLE, 0)
        self.assert_set(Parameter.POLLED_MODE, False)
        self.assert_set(Parameter.XMIT_POWER, 255)
        self.assert_set(Parameter.SPEED_OF_SOUND, 1485)
        self.assert_set(Parameter.PITCH, 0)
        self.assert_set(Parameter.ROLL, 0) 
        self.assert_set(Parameter.SALINITY, 35)
        self.assert_set(Parameter.SENSOR_SOURCE, "1111101")
        self.assert_set(Parameter.TIME_PER_PING, '00:01.00')
        self.assert_set(Parameter.FALSE_TARGET_THRESHOLD, '050,001')
        self.assert_set(Parameter.BANDWIDTH_CONTROL, 0)
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, 2000) 
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 704) 
        self.assert_set(Parameter.CLIP_DATA_PAST_BOTTOM, False)
        self.assert_set(Parameter.RECEIVER_GAIN_SELECT, 1)
        self.assert_set(Parameter.WATER_REFERENCE_LAYER, '001,005')
        self.assert_set(Parameter.NUMBER_OF_DEPTH_CELLS, 100)
        self.assert_set(Parameter.PINGS_PER_ENSEMBLE, 1)
        self.assert_set(Parameter.DEPTH_CELL_SIZE, 800)
        self.assert_set(Parameter.TRANSMIT_LENGTH, 0)
        self.assert_set(Parameter.PING_WEIGHT, 0)
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 175)

        """
        test a variety of paramater ranges.
        """

        # INSTRUMENT_ID -- Int 0-255
        self.assert_set_exception(Parameter.INSTRUMENT_ID, "LEROY JENKINS")
        self.assert_set_exception(Parameter.INSTRUMENT_ID, -1)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.INSTRUMENT_ID, 0)

        # SLEEP_ENABLE:  -- (0,1,2)
        self.assert_set(Parameter.SLEEP_ENABLE, 1)
        self.assert_set(Parameter.SLEEP_ENABLE, 2)

        self.assert_set_exception(Parameter.SLEEP_ENABLE, -1)
        self.assert_set_exception(Parameter.SLEEP_ENABLE, 3)
        self.assert_set_exception(Parameter.SLEEP_ENABLE, 3.1415926)
        self.assert_set_exception(Parameter.SLEEP_ENABLE, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.SLEEP_ENABLE, 0)

        # POLLED_MODE:  -- (True/False)
        self.assert_set(Parameter.POLLED_MODE, True)
        self.assert_set_exception(Parameter.POLLED_MODE, "LEROY JENKINS")
        # @TODO why does 5,-1 get turned to boolean
        #self.assert_set_exception(Parameter.POLLED_MODE, 5)
        #self.assert_set_exception(Parameter.POLLED_MODE, -1)
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.POLLED_MODE, False)

        # XMIT_POWER:  -- Int 0-255
        self.assert_set(Parameter.XMIT_POWER, 0)
        self.assert_set(Parameter.XMIT_POWER, 128)
        self.assert_set(Parameter.XMIT_POWER, 254)

        self.assert_set_exception(Parameter.XMIT_POWER, "LEROY JENKINS")
        self.assert_set_exception(Parameter.XMIT_POWER, 256)
        self.assert_set_exception(Parameter.XMIT_POWER, -1)
        self.assert_set_exception(Parameter.XMIT_POWER, 3.1415926)
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.XMIT_POWER, 255)

        # SPEED_OF_SOUND:  -- Int 1485 (1400 - 1600)
        self.assert_set(Parameter.SPEED_OF_SOUND, 1400)
        self.assert_set(Parameter.SPEED_OF_SOUND, 1450)
        self.assert_set(Parameter.SPEED_OF_SOUND, 1500)
        self.assert_set(Parameter.SPEED_OF_SOUND, 1550)
        self.assert_set(Parameter.SPEED_OF_SOUND, 1600)

        self.assert_set_exception(Parameter.SPEED_OF_SOUND, 0)
        self.assert_set_exception(Parameter.SPEED_OF_SOUND, 1399)

        self.assert_set_exception(Parameter.SPEED_OF_SOUND, 1601)
        self.assert_set_exception(Parameter.SPEED_OF_SOUND, "LEROY JENKINS")
        self.assert_set_exception(Parameter.SPEED_OF_SOUND, -256)
        self.assert_set_exception(Parameter.SPEED_OF_SOUND, -1)
        self.assert_set_exception(Parameter.SPEED_OF_SOUND, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.SPEED_OF_SOUND, 1485)

        # PITCH:  -- Int -6000 to 6000
        self.assert_set(Parameter.PITCH, -6000)
        self.assert_set(Parameter.PITCH, -4000)
        self.assert_set(Parameter.PITCH, -2000)
        self.assert_set(Parameter.PITCH, -1)
        self.assert_set(Parameter.PITCH, 0)
        self.assert_set(Parameter.PITCH, 1)
        self.assert_set(Parameter.PITCH, 2000)
        self.assert_set(Parameter.PITCH, 4000)
        self.assert_set(Parameter.PITCH, 6000)

        self.assert_set_exception(Parameter.PITCH, "LEROY JENKINS")
        self.assert_set_exception(Parameter.PITCH, -6001)
        self.assert_set_exception(Parameter.PITCH, 6001)
        self.assert_set_exception(Parameter.PITCH, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.PITCH, 0)

        # ROLL:  -- Int -6000 to 6000
        self.assert_set(Parameter.ROLL, -6000)
        self.assert_set(Parameter.ROLL, -4000)
        self.assert_set(Parameter.ROLL, -2000)
        self.assert_set(Parameter.ROLL, -1)
        self.assert_set(Parameter.ROLL, 0)
        self.assert_set(Parameter.ROLL, 1)
        self.assert_set(Parameter.ROLL, 2000)
        self.assert_set(Parameter.ROLL, 4000)
        self.assert_set(Parameter.ROLL, 6000)

        self.assert_set_exception(Parameter.ROLL, "LEROY JENKINS")
        self.assert_set_exception(Parameter.ROLL, -6001)
        self.assert_set_exception(Parameter.ROLL, 6001)
        self.assert_set_exception(Parameter.ROLL, 3.1415926)
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.ROLL, 0)

        # SALINITY:  -- Int (0 - 40)
        self.assert_set(Parameter.SALINITY, 0)
        self.assert_set(Parameter.SALINITY, 10)
        self.assert_set(Parameter.SALINITY, 20)
        self.assert_set(Parameter.SALINITY, 30)
        self.assert_set(Parameter.SALINITY, 40)

        self.assert_set_exception(Parameter.SALINITY, "LEROY JENKINS")

        # AssertionError: Unexpected exception: ES no value match (40 != -1)
        self.assert_set_exception(Parameter.SALINITY, -1)

        # AssertionError: Unexpected exception: ES no value match (35 != 41)
        self.assert_set_exception(Parameter.SALINITY, 41)

        self.assert_set_exception(Parameter.SALINITY, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.SALINITY, 35)

        # SENSOR_SOURCE:  -- (0/1) for 7 positions.
        # note it lacks capability to have a 1 in the #6 position
        self.assert_set(Parameter.SENSOR_SOURCE, "0000000")
        self.assert_set(Parameter.SENSOR_SOURCE, "1111101")
        self.assert_set(Parameter.SENSOR_SOURCE, "1010101")
        self.assert_set(Parameter.SENSOR_SOURCE, "0101000")
        self.assert_set(Parameter.SENSOR_SOURCE, "1100100")

        self.assert_set_exception(Parameter.SENSOR_SOURCE, "LEROY JENKINS")
        self.assert_set_exception(Parameter.SENSOR_SOURCE, 2)
        self.assert_set_exception(Parameter.SENSOR_SOURCE, -1)
        self.assert_set_exception(Parameter.SENSOR_SOURCE, "1111112")
        self.assert_set_exception(Parameter.SENSOR_SOURCE, "11111112")
        self.assert_set_exception(Parameter.SENSOR_SOURCE, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.SENSOR_SOURCE, "1111101")

        # TIME_PER_ENSEMBLE:  -- String 01:00:00.00 (hrs:min:sec.sec/100)
        self.assert_set(Parameter.TIME_PER_ENSEMBLE, "00:00:00.00")
        self.assert_set(Parameter.TIME_PER_ENSEMBLE, "00:00:01.00")
        self.assert_set(Parameter.TIME_PER_ENSEMBLE, "00:01:00.00")

        self.assert_set_exception(Parameter.TIME_PER_ENSEMBLE, '30:30:30.30')
        self.assert_set_exception(Parameter.TIME_PER_ENSEMBLE, '59:59:59.99')
        self.assert_set_exception(Parameter.TIME_PER_ENSEMBLE, "LEROY JENKINS")
        self.assert_set_exception(Parameter.TIME_PER_ENSEMBLE, 2)
        self.assert_set_exception(Parameter.TIME_PER_ENSEMBLE, -1)
        self.assert_set_exception(Parameter.TIME_PER_ENSEMBLE, '99:99:99.99')
        self.assert_set_exception(Parameter.TIME_PER_ENSEMBLE, '-1:-1:-1.+1')
        self.assert_set_exception(Parameter.TIME_PER_ENSEMBLE, 3.1415926)
        #
        # Reset to good value.
        #

        self.assert_set(Parameter.TIME_PER_ENSEMBLE, "00:00:00.00")

        # TIME_OF_FIRST_PING:  -- str ****/**/**,**:**:** (CCYY/MM/DD,hh:mm:ss)

        now_1_hour = (dt.datetime.utcnow() + dt.timedelta(hours=1)).strftime("%Y/%m/%d,%H:%m:%S")
        today_plus_10 = (dt.datetime.utcnow() + dt.timedelta(days=10)).strftime("%Y/%m/%d,%H:%m:%S")
        today_plus_1month = (dt.datetime.utcnow() + dt.timedelta(days=31)).strftime("%Y/%m/%d,%H:%m:%S")
        today_plus_6month = (dt.datetime.utcnow() + dt.timedelta(days=183)).strftime("%Y/%m/%d,%H:%m:%S")

        self.assert_set(Parameter.TIME_OF_FIRST_PING, now_1_hour)
        self.assert_set(Parameter.TIME_OF_FIRST_PING, today_plus_10)
        self.assert_set(Parameter.TIME_OF_FIRST_PING, today_plus_1month)
        self.assert_set(Parameter.TIME_OF_FIRST_PING, today_plus_6month)

        # AssertionError: Unexpected exception: TG no value match (2013/06/06,06:06:06 != LEROY JENKINS)
        self.assert_set_exception(Parameter.TIME_OF_FIRST_PING, "LEROY JENKINS")

        self.assert_set_exception(Parameter.TIME_OF_FIRST_PING, 2)
        self.assert_set_exception(Parameter.TIME_OF_FIRST_PING, -1)
        self.assert_set_exception(Parameter.TIME_OF_FIRST_PING, '99:99.99')
        self.assert_set_exception(Parameter.TIME_OF_FIRST_PING, '-1:-1.+1')
        self.assert_set_exception(Parameter.TIME_OF_FIRST_PING, 3.1415926)

        # TIME_PER_PING: '00:01.00'
        self.assert_set(Parameter.TIME_PER_PING, '01:00.00')
        self.assert_set(Parameter.TIME_PER_PING, '59:59.99')
        self.assert_set(Parameter.TIME_PER_PING, '30:30.30')

        self.assert_set_exception(Parameter.TIME_PER_PING, "LEROY JENKINS")
        self.assert_set_exception(Parameter.TIME_PER_PING, 2)
        self.assert_set_exception(Parameter.TIME_PER_PING, -1)
        self.assert_set_exception(Parameter.TIME_PER_PING, '99:99.99')
        self.assert_set_exception(Parameter.TIME_PER_PING, '-1:-1.+1')
        self.assert_set_exception(Parameter.TIME_PER_PING, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.TIME_PER_PING, '00:01.00')

        # FALSE_TARGET_THRESHOLD: string of 0-255,0-255
        self.assert_set(Parameter.FALSE_TARGET_THRESHOLD, "000,000")
        self.assert_set(Parameter.FALSE_TARGET_THRESHOLD, "255,000")
        self.assert_set(Parameter.FALSE_TARGET_THRESHOLD, "000,255")
        self.assert_set(Parameter.FALSE_TARGET_THRESHOLD, "255,255")

        self.assert_set_exception(Parameter.FALSE_TARGET_THRESHOLD, "256,000")
        self.assert_set_exception(Parameter.FALSE_TARGET_THRESHOLD, "256,255")
        self.assert_set_exception(Parameter.FALSE_TARGET_THRESHOLD, "000,256")
        self.assert_set_exception(Parameter.FALSE_TARGET_THRESHOLD, "255,256")
        self.assert_set_exception(Parameter.FALSE_TARGET_THRESHOLD, -1)

        self.assert_set_exception(Parameter.FALSE_TARGET_THRESHOLD, "LEROY JENKINS")

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.FALSE_TARGET_THRESHOLD, "050,001")

        # BANDWIDTH_CONTROL: 0/1,
        self.assert_set(Parameter.BANDWIDTH_CONTROL, 1)

        self.assert_set_exception(Parameter.BANDWIDTH_CONTROL, -1)
        self.assert_set_exception(Parameter.BANDWIDTH_CONTROL, 2)
        self.assert_set_exception(Parameter.BANDWIDTH_CONTROL, "LEROY JENKINS")
        self.assert_set_exception(Parameter.BANDWIDTH_CONTROL, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.BANDWIDTH_CONTROL, 0)

        # CORRELATION_THRESHOLD: int 064, 0 - 255
        self.assert_set(Parameter.CORRELATION_THRESHOLD, 50)
        self.assert_set(Parameter.CORRELATION_THRESHOLD, 100)
        self.assert_set(Parameter.CORRELATION_THRESHOLD, 150)
        self.assert_set(Parameter.CORRELATION_THRESHOLD, 200)
        self.assert_set(Parameter.CORRELATION_THRESHOLD, 255)

        self.assert_set_exception(Parameter.CORRELATION_THRESHOLD, "LEROY JENKINS")
        self.assert_set_exception(Parameter.CORRELATION_THRESHOLD, -256)
        self.assert_set_exception(Parameter.CORRELATION_THRESHOLD, -1)
        self.assert_set_exception(Parameter.CORRELATION_THRESHOLD, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.CORRELATION_THRESHOLD, 64)

        # ERROR_VELOCITY_THRESHOLD: int (0-5000 mm/s) NOTE it enforces 0-9999
        # decimals are truncated to ints
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, 0)
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, 128)
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, 1000)
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, 2000)
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, 3000)
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, 4000)
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, 5000)

        self.assert_set_exception(Parameter.ERROR_VELOCITY_THRESHOLD, "LEROY JENKINS")
        self.assert_set_exception(Parameter.ERROR_VELOCITY_THRESHOLD, -1)
        self.assert_set_exception(Parameter.ERROR_VELOCITY_THRESHOLD, 10000)
        self.assert_set_exception(Parameter.ERROR_VELOCITY_THRESHOLD, -3.1415926)
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, 2000)

        # BLANK_AFTER_TRANSMIT: int 704, (0 - 9999)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 0)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 128)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 1000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 2000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 3000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 4000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 5000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 6000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 7000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 8000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 9000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 9999)

        self.assert_set_exception(Parameter.BLANK_AFTER_TRANSMIT, "LEROY JENKINS")
        self.assert_set_exception(Parameter.BLANK_AFTER_TRANSMIT, -1)
        self.assert_set_exception(Parameter.BLANK_AFTER_TRANSMIT, 10000)
        self.assert_set_exception(Parameter.BLANK_AFTER_TRANSMIT, -3.1415926)
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 704)

        # CLIP_DATA_PAST_BOTTOM: True/False,
        self.assert_set(Parameter.CLIP_DATA_PAST_BOTTOM, True)

        self.assert_set_exception(Parameter.CLIP_DATA_PAST_BOTTOM, "LEROY JENKINS")
        # AssertionError: Unexpected exception: WI no value match (True != 5)
        #self.assert_set_exception(Parameter.CLIP_DATA_PAST_BOTTOM, 5)
        # AssertionError: Unexpected exception: WI no value match (True != -1)
        #self.assert_set_exception(Parameter.CLIP_DATA_PAST_BOTTOM, -1)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.CLIP_DATA_PAST_BOTTOM, False)

        # RECEIVER_GAIN_SELECT: (0/1),
        self.assert_set(Parameter.RECEIVER_GAIN_SELECT, 0)
        self.assert_set(Parameter.RECEIVER_GAIN_SELECT, 1)

        self.assert_set_exception(Parameter.RECEIVER_GAIN_SELECT, "LEROY JENKINS")
        self.assert_set_exception(Parameter.RECEIVER_GAIN_SELECT, 2)
        self.assert_set_exception(Parameter.RECEIVER_GAIN_SELECT, -1)
        self.assert_set_exception(Parameter.RECEIVER_GAIN_SELECT, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.RECEIVER_GAIN_SELECT, 1)

        # WATER_REFERENCE_LAYER:  -- int Begin Cell (0=OFF), End Cell  (0-100)
        self.assert_set(Parameter.WATER_REFERENCE_LAYER, "000,001")
        self.assert_set(Parameter.WATER_REFERENCE_LAYER, "000,100")
        self.assert_set(Parameter.WATER_REFERENCE_LAYER, "000,100")

        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, "255,000")
        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, "000,000")
        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, "001,000")
        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, "100,000")
        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, "000,101")
        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, "100,101")
        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, -1)
        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, 2)
        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, "LEROY JENKINS")
        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.WATER_REFERENCE_LAYER, "001,005")

        # NUMBER_OF_DEPTH_CELLS:  -- int (1-255) 100,
        self.assert_set(Parameter.NUMBER_OF_DEPTH_CELLS, 1)
        self.assert_set(Parameter.NUMBER_OF_DEPTH_CELLS, 128)
        self.assert_set(Parameter.NUMBER_OF_DEPTH_CELLS, 254)

        self.assert_set_exception(Parameter.NUMBER_OF_DEPTH_CELLS, "LEROY JENKINS")
        self.assert_set_exception(Parameter.NUMBER_OF_DEPTH_CELLS, 256)
        self.assert_set_exception(Parameter.NUMBER_OF_DEPTH_CELLS, 0)
        self.assert_set_exception(Parameter.NUMBER_OF_DEPTH_CELLS, -1)
        self.assert_set_exception(Parameter.NUMBER_OF_DEPTH_CELLS, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.NUMBER_OF_DEPTH_CELLS, 100)

        # PINGS_PER_ENSEMBLE: -- int  (0-16384) 1,
        self.assert_set(Parameter.PINGS_PER_ENSEMBLE, 0)
        self.assert_set(Parameter.PINGS_PER_ENSEMBLE, 16384)

        self.assert_set_exception(Parameter.PINGS_PER_ENSEMBLE, 16385)
        self.assert_set_exception(Parameter.PINGS_PER_ENSEMBLE, -1)
        self.assert_set_exception(Parameter.PINGS_PER_ENSEMBLE, 32767)
        self.assert_set_exception(Parameter.PINGS_PER_ENSEMBLE, 3.1415926)
        self.assert_set_exception(Parameter.PINGS_PER_ENSEMBLE, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.PINGS_PER_ENSEMBLE, 1)

        # DEPTH_CELL_SIZE: int 80 - 3200
        self.assert_set(Parameter.DEPTH_CELL_SIZE, 80)
        self.assert_set(Parameter.PINGS_PER_ENSEMBLE, 3200)

        self.assert_set_exception(Parameter.PING_WEIGHT, 3201)
        self.assert_set_exception(Parameter.PING_WEIGHT, -1)
        self.assert_set_exception(Parameter.PING_WEIGHT, 2)
        self.assert_set_exception(Parameter.PING_WEIGHT, 3.1415926)
        self.assert_set_exception(Parameter.PING_WEIGHT, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.PINGS_PER_ENSEMBLE, 0)

        # TRANSMIT_LENGTH: int 0 to 3200
        self.assert_set(Parameter.TRANSMIT_LENGTH, 80)
        self.assert_set(Parameter.TRANSMIT_LENGTH, 3200)

        self.assert_set_exception(Parameter.TRANSMIT_LENGTH, 3201)
        self.assert_set_exception(Parameter.TRANSMIT_LENGTH, -1)
        self.assert_set_exception(Parameter.TRANSMIT_LENGTH, 3.1415926)
        self.assert_set_exception(Parameter.TRANSMIT_LENGTH, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.TRANSMIT_LENGTH, 0)

        # PING_WEIGHT: (0/1),
        self.assert_set(Parameter.PING_WEIGHT, 0)
        self.assert_set(Parameter.PING_WEIGHT, 1)

        self.assert_set_exception(Parameter.PING_WEIGHT, 2)
        self.assert_set_exception(Parameter.PING_WEIGHT, -1)
        self.assert_set_exception(Parameter.PING_WEIGHT, 3.1415926)
        self.assert_set_exception(Parameter.PING_WEIGHT, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.PING_WEIGHT, 0)

        # AMBIGUITY_VELOCITY: int 2 - 700
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 2)
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 111)
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 222)
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 333)
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 444)
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 555)
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 666)
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 700)

        self.assert_set_exception(Parameter.AMBIGUITY_VELOCITY, 0)
        self.assert_set_exception(Parameter.AMBIGUITY_VELOCITY, 1)
        self.assert_set_exception(Parameter.AMBIGUITY_VELOCITY, -1)
        self.assert_set_exception(Parameter.AMBIGUITY_VELOCITY, 3.1415926)
        self.assert_set_exception(Parameter.AMBIGUITY_VELOCITY, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 175)

        # Test read only raise exceptions on set.
        self.assert_set_exception(Parameter.SERIAL_DATA_OUT, '000 000 111')
        self.assert_set_exception(Parameter.SERIAL_FLOW_CONTROL, '10110')
        self.assert_set_exception(Parameter.SAVE_NVRAM_TO_RECORDER, False)
        self.assert_set_exception(Parameter.SERIAL_OUT_FW_SWITCHES, '110100100')
        self.assert_set_exception(Parameter.WATER_PROFILING_MODE, 0)
        self.assert_set_exception(Parameter.BANNER, True)

    def test_commands(self):
        """
        Run instrument commands from both command and streaming mode.
        """
        self.assert_initialize_driver()
        ####
        # First test in command mode
        ####

        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

        self.assert_driver_command(ProtocolEvent.GET_CALIBRATION)
        self.assert_driver_command(ProtocolEvent.GET_CONFIGURATION)

        self.assert_driver_command(ProtocolEvent.CLOCK_SYNC)
        self.assert_driver_command(ProtocolEvent.SCHEDULED_CLOCK_SYNC)
        self.assert_driver_command(ProtocolEvent.SEND_LAST_SAMPLE, regex='^\x7f\x7fh.*')
        self.assert_driver_command(ProtocolEvent.SAVE_SETUP_TO_RAM, expected="Parameters saved as USER defaults")
        self.assert_driver_command(ProtocolEvent.GET_ERROR_STATUS_WORD, regex='^........')
        self.assert_driver_command(ProtocolEvent.CLEAR_ERROR_STATUS_WORD, regex='^Error Status Word Cleared')
        self.assert_driver_command(ProtocolEvent.GET_FAULT_LOG, regex='^Total Unique Faults   =.*')
        self.assert_driver_command(ProtocolEvent.CLEAR_FAULT_LOG, expected='FC ..........\r\n Fault Log Cleared.\r\nClearing buffer @0x00801000\r\nDone [i=2048].\r\n')
        self.assert_driver_command(ProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX, regex='^Beam Width:')
        self.assert_driver_command(ProtocolEvent.RUN_TEST_200, regex='^  Ambient  Temperature =')

        ####
        # Test in streaming mode
        ####
        # Put us in streaming
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_driver_command_exception(ProtocolEvent.SEND_LAST_SAMPLE, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.SAVE_SETUP_TO_RAM, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.GET_ERROR_STATUS_WORD, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.CLEAR_ERROR_STATUS_WORD, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.GET_FAULT_LOG, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.CLEAR_FAULT_LOG, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.RUN_TEST_200, exception_class=InstrumentCommandException)
        self.assert_driver_command(ProtocolEvent.SCHEDULED_CLOCK_SYNC)
        self.assert_driver_command_exception(ProtocolEvent.CLOCK_SYNC, exception_class=InstrumentCommandException)
        self.assert_driver_command(ProtocolEvent.GET_CALIBRATION, regex=r'Calibration date and time:')
        self.assert_driver_command(ProtocolEvent.GET_CONFIGURATION, regex=r' Instrument S/N')
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

        ####
        # Test a bad command
        ####
        self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)

    def test_autosample_particle_generation(self):
        """
        Test that we can generate particles when in autosample
        """
        self.assert_initialize_driver()

        params = {
            Parameter.INSTRUMENT_ID: 0,
            Parameter.SLEEP_ENABLE: 0,
            Parameter.POLLED_MODE: False,
            Parameter.XMIT_POWER: 255,
            Parameter.SPEED_OF_SOUND: 1485,
            Parameter.PITCH: 0,
            Parameter.ROLL: 0,
            Parameter.SALINITY: 35,
            Parameter.TIME_PER_ENSEMBLE: '00:00:20.00',
            Parameter.TIME_PER_PING: '00:01.00',
            Parameter.FALSE_TARGET_THRESHOLD: '050,001',
            Parameter.BANDWIDTH_CONTROL: 0,
            Parameter.CORRELATION_THRESHOLD: 64,
            Parameter.ERROR_VELOCITY_THRESHOLD: 2000,
            Parameter.BLANK_AFTER_TRANSMIT: 704,
            Parameter.CLIP_DATA_PAST_BOTTOM: 0,
            Parameter.RECEIVER_GAIN_SELECT: 1,
            Parameter.WATER_REFERENCE_LAYER: '001,005',
            Parameter.NUMBER_OF_DEPTH_CELLS: 100,
            Parameter.PINGS_PER_ENSEMBLE: 1,
            Parameter.DEPTH_CELL_SIZE: 800,
            Parameter.TRANSMIT_LENGTH: 0,
            Parameter.PING_WEIGHT: 0,
            Parameter.AMBIGUITY_VELOCITY: 175,
        }
        self.assert_set_bulk(params)

        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)

        self.assert_async_particle_generation(DataParticleType.ADCP_PD0_PARSED, self.assert_particle_pd0_data, timeout=40)

        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=10)

    def test_startup_params(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.

        since nose orders the tests by ascii value this should run first.
        """
        self.assert_initialize_driver()

        get_values = {
            Parameter.SERIAL_FLOW_CONTROL: '11110',
            Parameter.BANNER: False,
            Parameter.INSTRUMENT_ID: 0,
            Parameter.SLEEP_ENABLE: 0,
            Parameter.SAVE_NVRAM_TO_RECORDER: True,
            Parameter.POLLED_MODE: False,
            Parameter.XMIT_POWER: 255,
            Parameter.SPEED_OF_SOUND: 1485,
            Parameter.PITCH: 0,
            Parameter.ROLL: 0,
            Parameter.SALINITY: 35,
            Parameter.TIME_PER_ENSEMBLE: '00:00:00.00',
            Parameter.TIME_PER_PING: '00:01.00',
            Parameter.FALSE_TARGET_THRESHOLD: '050,001',
            Parameter.BANDWIDTH_CONTROL: 0,
            Parameter.CORRELATION_THRESHOLD: 64,
            Parameter.SERIAL_OUT_FW_SWITCHES: '111100000',
            Parameter.ERROR_VELOCITY_THRESHOLD: 2000,
            Parameter.BLANK_AFTER_TRANSMIT: 704,
            Parameter.CLIP_DATA_PAST_BOTTOM: 0,
            Parameter.RECEIVER_GAIN_SELECT: 1,
            Parameter.WATER_REFERENCE_LAYER: '001,005',
            Parameter.WATER_PROFILING_MODE: 1,
            Parameter.NUMBER_OF_DEPTH_CELLS: 100,
            Parameter.PINGS_PER_ENSEMBLE: 1,
            Parameter.DEPTH_CELL_SIZE: 800,
            Parameter.TRANSMIT_LENGTH: 0,
            Parameter.PING_WEIGHT: 0,
            Parameter.AMBIGUITY_VELOCITY: 175,
        }

        # Change the values of these parameters to something before the
        # driver is reinitalized.  They should be blown away on reinit.
        new_values = {
            Parameter.INSTRUMENT_ID: 1,
            Parameter.SLEEP_ENABLE: 1,
            Parameter.POLLED_MODE: True,
            Parameter.XMIT_POWER: 250,
            Parameter.SPEED_OF_SOUND: 1400,
            Parameter.PITCH: 1,
            Parameter.ROLL: 1,
            Parameter.SALINITY: 37,
            Parameter.TIME_PER_ENSEMBLE: '00:01:00.00',
            Parameter.TIME_PER_PING: '00:02.00',
            Parameter.FALSE_TARGET_THRESHOLD: '051,001',
            Parameter.BANDWIDTH_CONTROL: 1,
            Parameter.CORRELATION_THRESHOLD: 60,
            Parameter.ERROR_VELOCITY_THRESHOLD: 1900,
            Parameter.BLANK_AFTER_TRANSMIT: 710,
            Parameter.CLIP_DATA_PAST_BOTTOM: 1,
            Parameter.RECEIVER_GAIN_SELECT: 0,
            Parameter.WATER_REFERENCE_LAYER: '002,006',
            Parameter.NUMBER_OF_DEPTH_CELLS: 80,
            Parameter.PINGS_PER_ENSEMBLE: 2,
            Parameter.DEPTH_CELL_SIZE: 600,
            Parameter.TRANSMIT_LENGTH: 1,
            Parameter.PING_WEIGHT: 1,
            Parameter.AMBIGUITY_VELOCITY: 100,
        }

        self.assert_startup_parameters(self.assert_driver_parameters, new_values, get_values)

    ###
    #   Test scheduled events
    ###
    def assert_compass_calibration(self):
        """
        Verify a calibration particle was generated
        """
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.ADCP_COMPASS_CALIBRATION, self.assert_particle_compass_calibration, timeout=700)

    def test_scheduled_compass_calibration_command(self):
        """
        Verify the device configuration command can be triggered and run in command
        """
        self.assert_scheduled_event(ScheduledJob.GET_CALIBRATION, self.assert_compass_calibration, delay=300)
        self.assert_current_state(ProtocolState.COMMAND)

    def test_scheduled_compass_calibration_autosample(self):
        """
        Verify the device configuration command can be triggered and run in autosample
        """

        self.assert_scheduled_event(ScheduledJob.GET_CALIBRATION, self.assert_compass_calibration, delay=360, 
            autosample_command=ProtocolEvent.START_AUTOSAMPLE)
        self.assert_current_state(ProtocolState.AUTOSAMPLE)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE)

    def assert_acquire_status(self):
        """
        Verify a status particle was generated
        """
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.ADCP_SYSTEM_CONFIGURATION, self.assert_particle_system_configuration, timeout=300)

    def test_scheduled_device_configuration_command(self):
        """
        Verify the device status command can be triggered and run in command
        """
        self.assert_scheduled_event(ScheduledJob.GET_CONFIGURATION, self.assert_acquire_status, delay=360)
        self.assert_current_state(ProtocolState.COMMAND)

    def test_scheduled_device_configuration_autosample(self):
        """
        Verify the device status command can be triggered and run in autosample
        """
        self.assert_scheduled_event(ScheduledJob.GET_CONFIGURATION, self.assert_acquire_status,
                                    autosample_command=ProtocolEvent.START_AUTOSAMPLE, delay=300)
        self.assert_current_state(ProtocolState.AUTOSAMPLE)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE)

    def assert_clock_sync(self):
        """
        Verify the clock is set to at least the current date
        """
        #self.assert_initialize_driver()
        dt = self.assert_get(Parameter.TIME)
        lt = time.strftime("%Y/%m/%d,%H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        self.assertTrue(lt[:13].upper() in dt.upper())

    def test_scheduled_clock_sync_command(self):
        """
        Verify the scheduled clock sync is triggered and functions as expected
        """
        self.assert_scheduled_event(ScheduledJob.CLOCK_SYNC, self.assert_clock_sync, delay=200)
        self.assert_current_state(ProtocolState.COMMAND)

    def test_scheduled_clock_sync_autosample(self):
        """
        Verify the scheduled clock sync is triggered and functions as expected
        """
        self.assert_scheduled_event(ScheduledJob.CLOCK_SYNC, self.assert_clock_sync, 
                                    autosample_command=ProtocolEvent.START_AUTOSAMPLE, delay=350)
        self.assert_current_state(ProtocolState.AUTOSAMPLE)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class WorkhorseDriverQualificationTest(TeledyneQualificationTest, ADCPTMixin):
    def setUp(self):
        TeledyneQualificationTest.setUp(self)


    def assert_configuration(self, data_particle, verify_values = False):
        '''
        Verify assert_compass_calibration particle
        @param data_particle:  ADCP_COMPASS_CALIBRATION data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(ADCP_SYSTEM_CONFIGURATION_KEY, self._system_configuration_data_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_SYSTEM_CONFIGURATION)
        self.assert_data_particle_parameters(data_particle, self._system_configuration_data_parameters, verify_values)


    def assert_compass_calibration(self, data_particle, verify_values = False):
        '''
        Verify assert_compass_calibration particle
        @param data_particle:  ADCP_COMPASS_CALIBRATION data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(ADCP_COMPASS_CALIBRATION_KEY, self._calibration_data_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_COMPASS_CALIBRATION)
        self.assert_data_particle_parameters(data_particle, self._calibration_data_parameters, verify_values)

    # WORKS!! 4/22
    def test_autosample(self):
        """
        Verify autosample works and data particles are created
        """
        self.assert_enter_command_mode()

        self.assert_start_autosample()

        self.assert_particle_async(DataParticleType.ADCP_PD0_PARSED, self.assert_particle_pd0_data)
        self.assert_particle_polled(ProtocolEvent.GET_CALIBRATION, self.assert_compass_calibration, DataParticleType.ADCP_COMPASS_CALIBRATION, sample_count=1, timeout=20)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_configuration, DataParticleType.ADCP_SYSTEM_CONFIGURATION, sample_count=1, timeout=20)

        # Stop autosample and do run a couple commands.
        self.assert_stop_autosample()

        self.assert_particle_polled(ProtocolEvent.GET_CALIBRATION, self.assert_compass_calibration, DataParticleType.ADCP_COMPASS_CALIBRATION, sample_count=1)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_configuration, DataParticleType.ADCP_SYSTEM_CONFIGURATION, sample_count=1)

        # Restart autosample and gather a couple samples
        self.assert_sample_autosample(self.assert_particle_pd0_data, DataParticleType.ADCP_PD0_PARSED)

    # WORKS!! 4/22
    def assert_cycle(self):
        self.assert_start_autosample()

        self.assert_particle_async(DataParticleType.ADCP_PD0_PARSED, self.assert_particle_pd0_data)
        self.assert_particle_polled(ProtocolEvent.GET_CALIBRATION, self.assert_compass_calibration, DataParticleType.ADCP_COMPASS_CALIBRATION, sample_count=1, timeout=20)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_configuration, DataParticleType.ADCP_SYSTEM_CONFIGURATION, sample_count=1, timeout=20)

        # Stop autosample and do run a couple commands.
        self.assert_stop_autosample()

        self.assert_particle_polled(ProtocolEvent.GET_CALIBRATION, self.assert_compass_calibration, DataParticleType.ADCP_COMPASS_CALIBRATION, sample_count=1)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_configuration, DataParticleType.ADCP_SYSTEM_CONFIGURATION, sample_count=1)

    # WORKS!! 4/22
    def test_cycle(self):
        """
        Verify we can bounce between command and streaming.  We try it a few times to see if we can find a timeout.
        """
        self.assert_enter_command_mode()

        self.assert_cycle()
        self.assert_cycle()
        self.assert_cycle()
        self.assert_cycle()

    # need to override this because we are slow and dont feel like modifying the base class lightly
    def assert_set_parameter(self, name, value, verify=True):
        '''
        verify that parameters are set correctly.  Assumes we are in command mode.
        '''
        setParams = { name : value }
        getParams = [ name ]

        self.instrument_agent_client.set_resource(setParams, timeout=300)

        if(verify):
            result = self.instrument_agent_client.get_resource(getParams, timeout=300)
            self.assertEqual(result[name], value)

    # WORKS!! 4/23
    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """

        self.assert_enter_command_mode()
        self.assert_set_parameter(Parameter.SPEED_OF_SOUND, 1487)

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=600)

        self.tcp_client.send_data("%sEC1488%s" % (NEWLINE, NEWLINE))

        self.tcp_client.expect(Prompt.COMMAND)

        self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        self.assert_enter_command_mode()

        self.assert_get_parameter(Parameter.SPEED_OF_SOUND, 1488)

    # WORKS!! 4/23
    def test_execute_clock_sync(self):
        """
        Verify we can syncronize the instrument internal clock
        """
        self.assert_enter_command_mode()

        self.assert_execute_resource(ProtocolEvent.CLOCK_SYNC)

        # Now verify that at least the date matches
        check_new_params = self.instrument_agent_client.get_resource([Parameter.TIME], timeout=300)

        instrument_time = time.mktime(time.strptime(check_new_params.get(Parameter.TIME).lower(), "%Y/%m/%d,%H:%M:%S %Z"))

        self.assertLessEqual(abs(instrument_time - time.mktime(time.gmtime())), 15)

    # WORKS!! 4/23
    def test_get_capabilities(self):
        """
        @brief Verify that the correct capabilities are returned from get_capabilities
        at various driver/agent states.
        """
        self.assert_enter_command_mode()

        ##################
        #  Command Mode
        ##################
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.COMMAND),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [
                ProtocolEvent.CLOCK_SYNC,
                ProtocolEvent.START_AUTOSAMPLE,
                ProtocolEvent.CLEAR_ERROR_STATUS_WORD,
                ProtocolEvent.CLEAR_FAULT_LOG,
                ProtocolEvent.GET_CALIBRATION,
                ProtocolEvent.GET_CONFIGURATION,
                ProtocolEvent.GET_ERROR_STATUS_WORD,
                ProtocolEvent.GET_FAULT_LOG,
                ProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX,
                ProtocolEvent.RUN_TEST_200,
                ProtocolEvent.SAVE_SETUP_TO_RAM,
                ProtocolEvent.SEND_LAST_SAMPLE
                ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] =  [
            ProtocolEvent.STOP_AUTOSAMPLE,
            ProtocolEvent.GET_CONFIGURATION,
            ProtocolEvent.GET_CALIBRATION,
            ]
        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

        ##################
        #  DA Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.DIRECT_ACCESS)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = self._common_da_resource_commands()

        self.assert_direct_access_start_telnet()
        self.assert_capabilities(capabilities)
        self.assert_direct_access_stop_telnet()

        #######################
        #  Uninitialized Mode
        #######################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.UNINITIALIZED)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

        self.assert_reset()
        self.assert_capabilities(capabilities)

    # WORKS!! 4/23
    def test_startup_params_first_pass(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.  We have two identical versions
        of this test so it is run twice.  First time to check and CHANGE, then
        the second time to check again.

        since nose orders the tests by ascii value this should run second.
        """
        self.assert_enter_command_mode()

        self.assert_get_parameter(Parameter.SERIAL_FLOW_CONTROL, '11110') # Immutable
        self.assert_get_parameter(Parameter.BANNER, False)
        self.assert_get_parameter(Parameter.INSTRUMENT_ID, 0)
        self.assert_get_parameter(Parameter.SLEEP_ENABLE, 0)
        self.assert_get_parameter(Parameter.SAVE_NVRAM_TO_RECORDER, True) # Immutable
        self.assert_get_parameter(Parameter.POLLED_MODE, False)
        self.assert_get_parameter(Parameter.XMIT_POWER, 255)
        self.assert_get_parameter(Parameter.SPEED_OF_SOUND, 1485)
        self.assert_get_parameter(Parameter.PITCH, 0)
        self.assert_get_parameter(Parameter.ROLL, 0)
        self.assert_get_parameter(Parameter.SALINITY, 35)
        self.assert_get_parameter(Parameter.TIME_PER_ENSEMBLE, '00:00:00.00')
        self.assert_get_parameter(Parameter.TIME_PER_PING, '00:01.00')
        self.assert_get_parameter(Parameter.FALSE_TARGET_THRESHOLD, '050,001')
        self.assert_get_parameter(Parameter.BANDWIDTH_CONTROL, 0)
        self.assert_get_parameter(Parameter.CORRELATION_THRESHOLD, 64)
        self.assert_get_parameter(Parameter.SERIAL_OUT_FW_SWITCHES, '111100000') # Immutable
        self.assert_get_parameter(Parameter.ERROR_VELOCITY_THRESHOLD, 2000)
        self.assert_get_parameter(Parameter.BLANK_AFTER_TRANSMIT, 704)
        self.assert_get_parameter(Parameter.CLIP_DATA_PAST_BOTTOM, 0)
        self.assert_get_parameter(Parameter.RECEIVER_GAIN_SELECT, 1)
        self.assert_get_parameter(Parameter.WATER_REFERENCE_LAYER, '001,005')
        self.assert_get_parameter(Parameter.WATER_PROFILING_MODE, 1) # Immutable
        self.assert_get_parameter(Parameter.NUMBER_OF_DEPTH_CELLS, 100)
        self.assert_get_parameter(Parameter.PINGS_PER_ENSEMBLE, 1)
        self.assert_get_parameter(Parameter.DEPTH_CELL_SIZE, 800)
        self.assert_get_parameter(Parameter.TRANSMIT_LENGTH, 0)
        self.assert_get_parameter(Parameter.PING_WEIGHT, 0)
        self.assert_get_parameter(Parameter.AMBIGUITY_VELOCITY, 175)

        # Change these values anyway just in case it ran first.
        self.assert_set_parameter(Parameter.INSTRUMENT_ID, 1)
        self.assert_set_parameter(Parameter.SLEEP_ENABLE, 1)
        self.assert_set_parameter(Parameter.POLLED_MODE, True)
        self.assert_set_parameter(Parameter.XMIT_POWER, 250)
        self.assert_set_parameter(Parameter.SPEED_OF_SOUND, 1480)
        self.assert_set_parameter(Parameter.PITCH, 1)
        self.assert_set_parameter(Parameter.ROLL, 1)
        self.assert_set_parameter(Parameter.SALINITY, 36)
        self.assert_set_parameter(Parameter.TIME_PER_ENSEMBLE, '00:00:01.00')
        self.assert_set_parameter(Parameter.TIME_PER_PING, '00:02.00')
        self.assert_set_parameter(Parameter.FALSE_TARGET_THRESHOLD, '049,002')
        self.assert_set_parameter(Parameter.BANDWIDTH_CONTROL, 1)
        self.assert_set_parameter(Parameter.CORRELATION_THRESHOLD, 63)
        self.assert_set_parameter(Parameter.ERROR_VELOCITY_THRESHOLD, 1999)
        self.assert_set_parameter(Parameter.BLANK_AFTER_TRANSMIT, 714)
        self.assert_set_parameter(Parameter.CLIP_DATA_PAST_BOTTOM, 1)
        self.assert_set_parameter(Parameter.RECEIVER_GAIN_SELECT, 0)
        self.assert_set_parameter(Parameter.WATER_REFERENCE_LAYER, '002,006')
        self.assert_set_parameter(Parameter.NUMBER_OF_DEPTH_CELLS, 99)
        self.assert_set_parameter(Parameter.PINGS_PER_ENSEMBLE, 0)
        self.assert_set_parameter(Parameter.DEPTH_CELL_SIZE, 790)
        self.assert_set_parameter(Parameter.TRANSMIT_LENGTH, 1)
        self.assert_set_parameter(Parameter.PING_WEIGHT, 1)
        self.assert_set_parameter(Parameter.AMBIGUITY_VELOCITY, 176)

    # WORKS!! 4/23
    def test_startup_params_second_pass(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.  We have two identical versions
        of this test so it is run twice.  First time to check and CHANGE, then
        the second time to check again.

        since nose orders the tests by ascii value this should run second.
        """
        self.assert_enter_command_mode()

        self.assert_get_parameter(Parameter.SERIAL_FLOW_CONTROL, '11110') # Immutable
        self.assert_get_parameter(Parameter.BANNER, False)
        self.assert_get_parameter(Parameter.INSTRUMENT_ID, 0)
        self.assert_get_parameter(Parameter.SLEEP_ENABLE, 0)
        self.assert_get_parameter(Parameter.SAVE_NVRAM_TO_RECORDER, True) # Immutable
        self.assert_get_parameter(Parameter.POLLED_MODE, False)
        self.assert_get_parameter(Parameter.XMIT_POWER, 255)
        self.assert_get_parameter(Parameter.SPEED_OF_SOUND, 1485)
        self.assert_get_parameter(Parameter.PITCH, 0)
        self.assert_get_parameter(Parameter.ROLL, 0)
        self.assert_get_parameter(Parameter.SALINITY, 35)
        self.assert_get_parameter(Parameter.TIME_PER_ENSEMBLE, '00:00:00.00')
        self.assert_get_parameter(Parameter.TIME_PER_PING, '00:01.00')
        self.assert_get_parameter(Parameter.FALSE_TARGET_THRESHOLD, '050,001')
        self.assert_get_parameter(Parameter.BANDWIDTH_CONTROL, 0)
        self.assert_get_parameter(Parameter.CORRELATION_THRESHOLD, 64)
        self.assert_get_parameter(Parameter.SERIAL_OUT_FW_SWITCHES, '111100000') # Immutable
        self.assert_get_parameter(Parameter.ERROR_VELOCITY_THRESHOLD, 2000)
        self.assert_get_parameter(Parameter.BLANK_AFTER_TRANSMIT, 704)
        self.assert_get_parameter(Parameter.CLIP_DATA_PAST_BOTTOM, 0)
        self.assert_get_parameter(Parameter.RECEIVER_GAIN_SELECT, 1)
        self.assert_get_parameter(Parameter.WATER_REFERENCE_LAYER, '001,005')
        self.assert_get_parameter(Parameter.WATER_PROFILING_MODE, 1) # Immutable
        self.assert_get_parameter(Parameter.NUMBER_OF_DEPTH_CELLS, 100)
        self.assert_get_parameter(Parameter.PINGS_PER_ENSEMBLE, 1)
        self.assert_get_parameter(Parameter.DEPTH_CELL_SIZE, 800)
        self.assert_get_parameter(Parameter.TRANSMIT_LENGTH, 0)
        self.assert_get_parameter(Parameter.PING_WEIGHT, 0)
        self.assert_get_parameter(Parameter.AMBIGUITY_VELOCITY, 175)

        # Change these values anyway just in case it ran first.
        self.assert_set_parameter(Parameter.INSTRUMENT_ID, 1)
        self.assert_set_parameter(Parameter.SLEEP_ENABLE, 1)
        self.assert_set_parameter(Parameter.POLLED_MODE, True)
        self.assert_set_parameter(Parameter.XMIT_POWER, 250)
        self.assert_set_parameter(Parameter.SPEED_OF_SOUND, 1480)
        self.assert_set_parameter(Parameter.PITCH, 1)
        self.assert_set_parameter(Parameter.ROLL, 1)
        self.assert_set_parameter(Parameter.SALINITY, 36)
        self.assert_set_parameter(Parameter.TIME_PER_ENSEMBLE, '00:00:01.00')
        self.assert_set_parameter(Parameter.TIME_PER_PING, '00:02.00')
        self.assert_set_parameter(Parameter.FALSE_TARGET_THRESHOLD, '049,002')
        self.assert_set_parameter(Parameter.BANDWIDTH_CONTROL, 1)
        self.assert_set_parameter(Parameter.CORRELATION_THRESHOLD, 63)
        self.assert_set_parameter(Parameter.ERROR_VELOCITY_THRESHOLD, 1999)
        self.assert_set_parameter(Parameter.BLANK_AFTER_TRANSMIT, 714)
        self.assert_set_parameter(Parameter.CLIP_DATA_PAST_BOTTOM, 1)
        self.assert_set_parameter(Parameter.RECEIVER_GAIN_SELECT, 0)
        self.assert_set_parameter(Parameter.WATER_REFERENCE_LAYER, '002,006')
        self.assert_set_parameter(Parameter.NUMBER_OF_DEPTH_CELLS, 99)
        self.assert_set_parameter(Parameter.PINGS_PER_ENSEMBLE, 0)
        self.assert_set_parameter(Parameter.DEPTH_CELL_SIZE, 790)
        self.assert_set_parameter(Parameter.TRANSMIT_LENGTH, 1)
        self.assert_set_parameter(Parameter.PING_WEIGHT, 1)
        self.assert_set_parameter(Parameter.AMBIGUITY_VELOCITY, 176)


###############################################################################
#                             PUBLICATION TESTS                               #
# Device specific pulication tests are for                                    #
# testing device specific capabilities                                        #
###############################################################################
@attr('PUB', group='mi')
class WorkhorseDriverPublicationTest(TeledynePublicationTest):
    def setUp(self):
        TeledynePublicationTest.setUp(self)

    def test_granule_generation(self):
        self.assert_initialize_driver()

        # Currently these tests only verify that the data granule is generated, but the values
        # are not tested.  We will eventually need to replace log.debug with a better callback
        # function that actually tests the granule.
        self.assert_sample_async("raw data", log.debug, DataParticleType.RAW, timeout=10)
        self.assert_sample_async(SAMPLE_RAW_DATA, log.debug, DataParticleType.ADCP_PD0_PARSED, timeout=10)
        self.assert_sample_async(PS0_RAW_DATA, log.debug, DataParticleType.ADCP_SYSTEM_CONFIGURATION, timeout=10)
        self.assert_sample_async(CALIBRATION_RAW_DATA, log.debug, DataParticleType.ADCP_COMPASS_CALIBRATION, timeout=10)
