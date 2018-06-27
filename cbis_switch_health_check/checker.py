#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import print_function
import abc
import sqlite3
import os

PATH = os.path.dirname(os.path.abspath(__file__))


def get_db_connection(self, in_memory=False):
    if in_memory:
        return sqlite3.connect(':memory:')
    else:
        return sqlite3.connect(PATH + '/' + self.switch_ip + '.db')


class BaseCheck(object):
    def __init__(self):
        pass

    @abc.abstractmethod
    def cmd(self):
        raise NotImplemented()

    @abc.abstractmethod
    def call_back(self, data, timestamp):
        raise NotImplemented()


class InterfaceStatus(BaseCheck):

    def cmd(self):
        return 'show interfaces description | except "unused port|Vlan" | grep "NO  admin" | no-more'

    def call_back(self, data, timestamp):
        for line in data.splitlines():
            if not line:
                continue
            if 'show ' not in line:
                return ['Interface Status', 'NOK']
        return ['Interface Status', 'OK']


class SystemStatus(BaseCheck):

    def cmd(self):
        return 'show system | grep "down" | no-more'

    def call_back(self, data, timestamp):
        for line in data.splitlines():
            if not line:
                continue
            if 'show ' not in line:
                return ['System Status', 'NOK']

        return ['System Status', 'OK']


class VLTStatus(BaseCheck):

    def cmd(self):
        return 'show vlt brief | grep "down|no" | no-more'

    def call_back(self, data, timestamp):
        for line in data.splitlines():
            if not line:
                continue
            if 'show ' not in line:
                return ['VLT Status', 'NOK']

        return ['VLT Status', 'OK']


class FEFDStatus(BaseCheck):

    def cmd(self):
        return 'show fefd | grep "Unknown|Err-disabled" ignore-case | no-more'

    def call_back(self, data, timestamp):
        for line in data.splitlines():
            if not line:
                continue
            if 'show ' not in line:
                return ['FEFD Status', 'NOK']

        return ['FEFD Status', 'OK']


class AlarmStatus(BaseCheck):

    def cmd(self):
        return 'show alarms | except "Controlling Bridge:|Minor Alarms|No minor alarms|Major Alarms|No major alarms|===|-----|Alarm Type" | no-more'

    def call_back(self, data, timestamp):
        for line in data.splitlines():
            if not line:
                continue
            if 'show ' not in line:
                return ['Alarm Status', 'NOK']

        return ['Alarm Status', 'OK']


class CPUStatus(BaseCheck):

    def cmd(self):
        return 'show processes cpu management-unit | grep "CPU utilization" | no-more'

    def call_back(self, data, timestamp):
        for line in data.splitlines():
            if not line or 'show process' in line:
                continue
            if 'CPU utilization ' in line:
                values = line.split(";")
                values2 = values[2].split(':')
                cpu = values2[1].strip().replace('%', '')
                if float(cpu) > 50:
                    return ['CPU Status', 'NOK']

        return ['CPU Status', 'OK']


class MemoryStatus(BaseCheck):

    def cmd(self):
        return 'show processes memory management-unit | gr "Total|CurrentUsed:|SharedUsed :" | no-more'

    def call_back(self, data, timestamp):
        total = 0
        current_used = 0
        for line in data.splitlines():
            if not line or 'show process' in line:
                continue
            if 'Total' in line:
                values = line.split(",")
                values2 = values[0].split(':')
                total = values2[1].strip()
            if 'CurrentUsed' in line:
                values = line.split(",")
                values2 = values[0].split(':')
                current_used = values2[1].strip()

        percent = (float(current_used) / float(total)) * 100
        if percent > 50:
            return ['Memory Status', 'NOK']

        return ['Memory Status', 'OK']






if __name__ == '__main__':
    text = "Total      :  3203289088, MaxUsed    :  1254072320 [05/21/2018 08:03:16]"
    values = text.split(',')
    values2 = values[0].split(':')
    cpu = values2[1].strip()
    print(cpu)