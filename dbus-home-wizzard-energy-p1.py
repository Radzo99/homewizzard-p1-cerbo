#!/usr/bin/env python
# vim: ts=2 sw=2 et

# import normal packages
import platform
import logging
import logging.handlers
import sys
import os
import sys
if sys.version_info.major == 2:
    import gobject
else:
    from gi.repository import GLib as gobject
import sys
import time
import requests # for http GET
import configparser # for config/ini file

# our own packages from victron
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
from vedbus import VeDbusService


class DbusHomeWizzardEnergyP1Service:
    def __init__(self, paths, productname='Home Wizzard Energy P1', connection='Home Wizzard Energy P1 HTTP JSOn service'):
        config = self._getConfig()
        deviceinstance = int(config['DEFAULT']['DeviceInstance'])
        customname = config['DEFAULT']['CustomName']
        role = config['DEFAULT']['Role']

        allowed_roles = ['pvinverter','grid']
        if role in allowed_roles:
            servicename = 'com.victronenergy.' + role
        else:
            logging.error("Configured Role: %s is not in the allowed list")
            exit()

        if role == 'pvinverter':
            productid = 0xA144
        else:
            productid = 45069

        self._dbusservice = VeDbusService("{}.http_{:02d}".format(servicename, deviceinstance))
        self._paths = paths

        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', productid)
        self._dbusservice.add_path('/DeviceType', 345)
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/CustomName', customname)
        self._dbusservice.add_path('/Latency', None)
        self._dbusservice.add_path('/FirmwareVersion', 0.2)
        self._dbusservice.add_path('/HardwareVersion', 0)
        self._dbusservice.add_path('/Connected', 1)
        self._dbusservice.add_path('/Role', role)
        self._dbusservice.add_path('/Position', self._getP1Position())
        self._dbusservice.add_path('/Serial', self._getP1Serial())
        self._dbusservice.add_path('/UpdateIndex', 0)

        # add path values to dbus
        for path, settings in self._paths.items():
          self._dbusservice.add_path(
            path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue)

        # last update
        self._lastUpdate = 0

        # add _update function 'timer'
        gobject.timeout_add(500, self._update) # pause 500ms before the next request

        # add _signOfLife 'timer' to get feedback in log every 5minutes
        gobject.timeout_add(self._getSignOfLifeInterval()*60*1000, self._signOfLife)

    def _getP1Serial(self):
        meter_data = self._getP1Data()

        if not meter_data['unique_id']:
            raise ValueError("Response does not contain 'unique_id' attribute")

        serial = meter_data['unique_id']
        return serial

    def _getConfig(self):
        config = configparser.ConfigParser()
        config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
        return config;

    def _getSignOfLifeInterval(self):
        config = self._getConfig()
        value = config['DEFAULT']['SignOfLifeLog']

        if not value:
            value = 0

        return int(value)

    def _getP1Position(self):
        config = self._getConfig()
        value = config['DEFAULT']['Position']

        if not value:
            value = 0

        return int(value)

    def _getP1StatusUrl(self):
        config = self._getConfig()
        accessType = config['DEFAULT']['AccessType']

        if accessType == 'OnPremise':
            URL = "http://%s/api/v1/data" % (config['ONPREMISE']['Host'])
        else:
            raise ValueError("AccessType %s is not supported" % (config['DEFAULT']['AccessType']))

        return URL

    def _getP1Data(self):
        URL = self._getP1StatusUrl()
        meter_r = requests.get(url = URL, timeout=5)

        # check for response
        if not meter_r:
            raise ConnectionError("No response from Home Wizzard Energy - %s" % (URL))

        meter_data = meter_r.json()

        # check for Json
        if not meter_data:
            raise ValueError("Converting response to JSON failed")

        return meter_data

    def _signOfLife(self):
        logging.info("--- Start: sign of life ---")
        logging.info("Last _update() call: %s" % (self._lastUpdate))
        logging.info("Last '/Ac/Power': %s" % (self._dbusservice['/Ac/Power']))
        logging.info("--- End: sign of life ---")
        return True

    def _update(self):
        try:
            meter_data = self._getP1Data()
            config = self._getConfig()
            phases = config['DEFAULT']['Phases']

            if phases == '1':
                # Phases = 1: monofasig of LGF5E360 op 3x230V net.
                # Gebruik active_power_w als totaalvermogen voor L1.
                # Stroomteken volgt het teken van het vermogen:
                # - vermogen positief (afname) → stroom positief
                # - vermogen negatief (injectie) → stroom negatief
                power_total = meter_data['active_power_w']
                l1_current_raw = meter_data['active_current_l1_a']
                # Stroomteken aanpassen: negatief als vermogen negatief is
                l1_current = -abs(l1_current_raw) if power_total < 0 else abs(l1_current_raw)

                self._dbusservice['/Ac/Power']      = power_total
                self._dbusservice['/Ac/L1/Voltage'] = meter_data['active_voltage_l1_v']
                self._dbusservice['/Ac/L1/Current'] = l1_current
                self._dbusservice['/Ac/L1/Power']   = power_total  # FIX: totaal ipv active_power_l1_w (= 0)
                self._dbusservice['/Ac/L2/Power']   = 0
                self._dbusservice['/Ac/L3/Power']   = 0
                self._dbusservice['/Ac/L2/Voltage'] = 0
                self._dbusservice['/Ac/L3/Voltage'] = 0
                self._dbusservice['/Ac/L2/Current'] = 0
                self._dbusservice['/Ac/L3/Current'] = 0
                self._dbusservice['/Ac/Energy/Forward']    = (meter_data['total_power_import_kwh'] / 1000)
                self._dbusservice['/Ac/Energy/Reverse']    = (meter_data['total_power_export_kwh'] / 1000)
                self._dbusservice['/Ac/L1/Energy/Forward'] = (meter_data['total_power_import_kwh'] / 1000)
                self._dbusservice['/Ac/L1/Energy/Reverse'] = (meter_data['total_power_export_kwh'] / 1000)

            if phases == '3':
                # Phases = 3: 3-fasig net met correcte per-fase waarden (bv. Fluvius).
                # Stroomteken volgt het teken van het vermogen per fase:
                # - vermogen positief (afname) → stroom positief
                # - vermogen negatief (injectie) → stroom negatief
                l1_power = meter_data['active_power_l1_w']
                l2_power = meter_data['active_power_l2_w']
                l3_power = meter_data['active_power_l3_w']
                # Stroomteken aanpassen per fase
                l1_current = -abs(meter_data['active_current_l1_a']) if l1_power < 0 else abs(meter_data['active_current_l1_a'])
                l2_current = -abs(meter_data['active_current_l2_a']) if l2_power < 0 else abs(meter_data['active_current_l2_a'])
                l3_current = -abs(meter_data['active_current_l3_a']) if l3_power < 0 else abs(meter_data['active_current_l3_a'])

                self._dbusservice['/Ac/Power']      = meter_data['active_power_w']
                self._dbusservice['/Ac/L1/Voltage'] = meter_data['active_voltage_l1_v']
                self._dbusservice['/Ac/L2/Voltage'] = meter_data['active_voltage_l2_v']
                self._dbusservice['/Ac/L3/Voltage'] = meter_data['active_voltage_l3_v']
                self._dbusservice['/Ac/L1/Current'] = l1_current
                self._dbusservice['/Ac/L2/Current'] = l2_current
                self._dbusservice['/Ac/L3/Current'] = l3_current
                self._dbusservice['/Ac/L1/Power']   = l1_power
                self._dbusservice['/Ac/L2/Power']   = l2_power
                self._dbusservice['/Ac/L3/Power']   = l3_power
                self._dbusservice['/Ac/Energy/Forward'] = (meter_data['total_power_import_kwh'] / 1000)
                self._dbusservice['/Ac/Energy/Reverse'] = (meter_data['total_power_export_kwh'] / 1000)

            logging.debug("House Consumption (/Ac/Power): %s" % (self._dbusservice['/Ac/Power']))
            logging.debug("House Forward (/Ac/Energy/Forward): %s" % (self._dbusservice['/Ac/Energy/Forward']))
            logging.debug("House Reverse (/Ac/Energy/Revers): %s" % (self._dbusservice['/Ac/Energy/Reverse']))
            logging.debug("---")

            self._dbusservice['/UpdateIndex'] = (self._dbusservice['/UpdateIndex'] + 1) % 256
            self._lastUpdate = time.time()

        except (ValueError, requests.exceptions.ConnectionError, requests.exceptions.Timeout, ConnectionError) as e:
            logging.critical('Error getting data from Home Wizzard - check network or P1 status. Details: %s', e, exc_info=e)
            self._dbusservice['/Ac/L1/Power'] = 0
            self._dbusservice['/Ac/L2/Power'] = 0
            self._dbusservice['/Ac/L3/Power'] = 0
            self._dbusservice['/Ac/Power'] = 0
            self._dbusservice['/UpdateIndex'] = (self._dbusservice['/UpdateIndex'] + 1) % 256
        except Exception as e:
            logging.critical('Error at %s', '_update', exc_info=e)

        return True

    def _handlechangedvalue(self, path, value):
        logging.debug("someone else updated %s to %s" % (path, value))
        return True


def getLogLevel():
    config = configparser.ConfigParser()
    config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
    logLevelString = config['DEFAULT']['LogLevel']

    if logLevelString:
        level = logging.getLevelName(logLevelString)
    else:
        level = logging.INFO

    return level


def main():
    logging.basicConfig(format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=getLogLevel(),
        handlers=[
            logging.FileHandler("%s/current.log" % (os.path.dirname(os.path.realpath(__file__)))),
            logging.StreamHandler()
        ])

    try:
        logging.info("Start")

        from dbus.mainloop.glib import DBusGMainLoop
        DBusGMainLoop(set_as_default=True)

        _kwh = lambda p, v: (str(round(v, 2)) + ' kWh')
        _a   = lambda p, v: (str(round(v, 1)) + ' A')
        _w   = lambda p, v: (str(round(v, 1)) + ' W')
        _v   = lambda p, v: (str(round(v, 1)) + ' V')

        config = configparser.ConfigParser()
        config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
        phases = config['DEFAULT']['Phases']

        # Basispaden altijd aanwezig
        paths = {
            '/Ac/Energy/Forward': {'initial': 0, 'textformat': _kwh},
            '/Ac/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
            '/Ac/Power':          {'initial': 0, 'textformat': _w},
            '/Ac/Current':        {'initial': 0, 'textformat': _a},
            '/Ac/Voltage':        {'initial': 0, 'textformat': _v},
            '/Ac/L1/Voltage':     {'initial': 0, 'textformat': _v},
            '/Ac/L1/Current':     {'initial': 0, 'textformat': _a},
            '/Ac/L1/Power':       {'initial': 0, 'textformat': _w},
            '/Ac/L1/Energy/Forward': {'initial': 0, 'textformat': _kwh},
            '/Ac/L1/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
        }

        # L2 en L3 enkel toevoegen bij 3-fase
        if phases == '3':
            paths.update({
                '/Ac/L2/Voltage': {'initial': 0, 'textformat': _v},
                '/Ac/L3/Voltage': {'initial': 0, 'textformat': _v},
                '/Ac/L2/Current': {'initial': 0, 'textformat': _a},
                '/Ac/L3/Current': {'initial': 0, 'textformat': _a},
                '/Ac/L2/Power':   {'initial': 0, 'textformat': _w},
                '/Ac/L3/Power':   {'initial': 0, 'textformat': _w},
            })

        pvac_output = DbusHomeWizzardEnergyP1Service(paths=paths)

        logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
        mainloop = gobject.MainLoop()
        mainloop.run()

    except (ValueError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        logging.critical('Error in main type %s', str(e))
    except Exception as e:
        logging.critical('Error at %s', 'main', exc_info=e)

if __name__ == "__main__":
    main()
