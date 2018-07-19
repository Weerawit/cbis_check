#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import print_function
import abc
import os
import re
import contextlib

PATH = os.path.dirname(os.path.abspath(__file__))


class BaseCheck(object):
    def __init__(self):
        pass

    @abc.abstractmethod
    def cmd(self):
        raise NotImplemented()

    @abc.abstractmethod
    def call_back(self, data, timestamp):
        raise NotImplemented()


class GenericCheck(BaseCheck):
    def __init__(self, cmd_str, title=None):
        self.cmd_str = cmd_str
        self.cmd_title = cmd_str.split('|')[0].strip()
        if title is None:
            self.title = self.cmd_title
        else:
            self.title = title

    def cmd(self):
        return self.cmd_str

    def call_back(self, data, timestamp):
        lines = data.splitlines()
        i = 0
        while i < len(lines) - 1:
            line = lines[i]
            i += 1
            if not line:
                continue
            if self.cmd_title not in line:
                return [self.title, 'NOK']
        return [self.title, 'OK']


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


class CRCError(BaseCheck):

    def __init__(self, engine):
        self.engine = engine

    def cmd(self):
        return 'show interfaces | grep "twentyFiveGigE|hundredGigE|tengigabit|fortyGigE|CRC" | no-more'

    def call_back(self, data, timestamp):
        conn = self.engine.get_db_connection()
        is_error = False
        with contextlib.closing(conn):
            conn.execute('CREATE TABLE IF NOT EXISTS crc_interfaces (key text, value text)')

            rows = conn.execute('SELECT key, value from crc_interfaces')
            previous_values = dict([(k, v) for k, v in rows])

            conn.execute('delete from crc_interfaces')

            current_values = {}
            lines = data.splitlines()
            i = 0
            while i < len(lines):
                line = lines[i]
                i += 1
                if not line or 'show interfaces' in line:
                    continue
                match = re.match('^(?P<if_name>(twentyFiveGigE|hundredGigE|tengigabit|fortyGigE) .*?\s)', line)
                if match is not None:
                    if_name = match.groupdict()['if_name'].strip()
                    next_line = lines[i]
                    i += 1
                    if 'CRC' in next_line:
                        values = next_line.split(',')
                        values2 = values[0].strip().split(' ')
                        crc = values2[0].strip()
                        current_values[if_name] = crc

            #compare with previous values
            for key in current_values:
                current_value = current_values.get(key)
                previous_value = previous_values.get(key)
                if abs(int(current_value) - int(previous_value) >= 1000) and current_value != '0':
                    is_error = True

                conn.execute('insert into crc_interfaces (key, value) values (?, ?)', (key, current_value))

            conn.commit()

        if is_error:
            return ['CRC Error', 'NOK']

        return ['CRC Error', 'OK']


class FECError(BaseCheck):

    def __init__(self, engine):
        self.engine = engine

    def cmd(self):
        return 'show interfaces | grep "twentyFiveGigE|hundredGigE|FEC" | except "FEC status is" | except "Forward Error" | no-more'

    def call_back(self, data, timestamp):
        conn = self.engine.get_db_connection()
        is_error = False
        with contextlib.closing(conn):
            conn.execute('CREATE TABLE IF NOT EXISTS fec_interfaces (key text, value text)')

            rows = conn.execute('SELECT key, value from fec_interfaces')
            previous_values = dict([(k, v) for k, v in rows])

            conn.execute('delete from fec_interfaces')

            current_values = {}
            lines = data.splitlines()
            i = 0
            while i < len(lines):
                line = lines[i]
                i += 1
                if not line or 'show interfaces' in line:
                    continue
                match = re.match('^(?P<if_name>(twentyFiveGigE|hundredGigE|tengigabit|fortyGigE) .*?\s)', line)
                if match is not None:
                    if_name = match.groupdict()['if_name'].strip()
                    next_line = lines[i]
                    i += 1
                    if 'FEC bit' in next_line:
                        values = next_line.split(',')
                        values2 = values[0].strip().split(' ')
                        fec = values2[0].strip()
                        current_values[if_name] = fec

            #compare with previous values
            for key in current_values:
                current_value = current_values.get(key)
                previous_value = previous_values.get(key)
                if current_values != previous_value and current_value != '0':
                    is_error = True

                conn.execute('insert into fec_interfaces (key, value) values (?, ?)', (key, current_value))

            conn.commit()

        if is_error:
            return ['FEC Error', 'NOK']

        return ['FEC Error', 'OK']


if __name__ == '__main__':
    text = "     0 CRC, 0 overrun, 0 discarded"
    values = text.split(',')
    values2 = values[0].strip().split(' ')
    cpu = values2[0].strip()
    print(cpu)