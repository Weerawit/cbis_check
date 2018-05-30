#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import print_function

import argparse
import sys
import os
import logging.config
import sqlite3
import subprocess
import re
import datetime
from prettytable import PrettyTable
import uuid
from checker import *


PATH = os.path.dirname(os.path.abspath(__file__))

logger = logging.getLogger(__name__)
logging.config.fileConfig(os.path.join(PATH, 'logging.ini'), disable_existing_loggers=False)


class CheckEngine(object):

    def __init__(self, uc, test_flag, output_file, output_csv_file):
        self.uc = uc
        self.test_flag = test_flag
        self.output_file = output_file
        self.output_csv_file = output_csv_file

    def _format(self, checker, output_file, output_csv_file):

        table = PrettyTable(['host', 'status'])
        table.align["host"] = "l"
        table.title = checker.__doc__
        table.title_align = 'l'
        table.header_style = 'title'
        output = checker.check()
        line_list = output.splitlines()

        csv_records = []
        if len(line_list) > 0:
            for line in output.splitlines():
                if line:
                    data = line.split(',')
                    table.add_row(data)
                    csv_records.append(data)
        else:
            table.add_row(['all', 'OK'])
            csv_records.append(['all', 'OK'])

        output_file.write('%s\n' % table)
        output_file.flush()

        for record in csv_records:
            output_csv_file.write('"%s",%s,%s\n' % (checker.__doc__.replace('\n', ' '), record[0], record[1]))
        output_csv_file.flush()

    def check_all(self):
        checker_list = [cls(self) for cls in BaseCheck.__subclasses__()]
        with open(self.output_file, 'wb') as f, open(self.output_csv_file, 'wb') as f_csv:
            for checker in checker_list:
                self._format(checker, output_file=f, output_csv_file=f_csv)

    def check(self, args):
        with open(self.output_file, 'wb') as f, open(self.output_csv_file, 'wb') as f_csv:
            for arg_name in args:
                cls = globals()[arg_name]
                self._format(cls(self), output_file=f, output_csv_file=f_csv)

    def run_shell(self, cmd):

        logger.info('Executing on %s with command %s' % (self.uc, cmd))

        if self.test_flag:
            ssh_cmd = cmd.split(' ')
        else:
            ssh_cmd = ["ssh", "-o", "LogLevel=error", "stack@%s" % self.uc, cmd]

        return subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE)

    def run_xargs(self, host_pattern, cmd, callback):
        now = datetime.datetime.now()

        temp_file_name = '/tmp/post_check_%s' % str(uuid.uuid4())

        if host_pattern == '*':
            host_pattern = 'overcloud-*'
        if self.test_flag:
            cmd = cmd
        elif host_pattern == 'undercloud':
            cmd = 'echo \"hostname: `hostname`\"; %s ' % cmd
        else:
            cmd_host = 'grep -E \'%s\' /etc/hosts > %s' % (host_pattern, temp_file_name)
            self.run_shell(cmd_host).wait()

            cmd = "while read -r name <&3; do ssh -o ConnectTimeout=3 -o LogLevel=error " \
                  "-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no " \
                  "cbis-admin@\"$name\" 'echo \"hostname: `hostname`\"; %s ' || true; done 3< %s; rm %s" % \
                  (cmd, temp_file_name, temp_file_name)

        hostname_re = re.compile('hostname: ')

        proc = self.run_shell(cmd)
        stdout, stderr = proc.communicate()
        if proc.returncode == 0:
            lines = stdout.splitlines()
            i = 0
            while i < len(lines):
                line = lines[i]
                line_each_node = ''
                if hostname_re.search(line):
                    hostname = line.split(':')[1].strip()
                    i += 1
                    next_line = lines[i]
                    while not hostname_re.search(next_line):
                        line_each_node += '%s\n\r' % next_line
                        i += 1
                        try:
                            next_line = lines[i]
                        except IndexError:
                            break
                    callback(hostname, line_each_node, now)
                else:
                    i += 1

        else:
            logger.error('Cannot execute command %s ' % cmd)
            raise RuntimeError('Cannot execute command %s ' % cmd)

    def run_salt(self, host_pattern, cmd, callback):
        now = datetime.datetime.now()
        if self.test_flag:
            cmd = cmd
        else:
            cmd = "salt --no-color '%s' cmd.run 'echo \"hostname: `hostname`\"; %s' " % (host_pattern, cmd)

        salt_re = re.compile('^(compute|controller|cephstorage)-\d*:')
        hostname_re = re.compile('hostname: ')

        proc = self.run_shell(cmd)
        stdout, stderr = proc.communicate()
        if proc.returncode == 0:
            lines = stdout.splitlines()
            i = 0
            while i < len(lines):
                line = lines[i]
                line_each_node = ''
                if salt_re.match(line):
                    i += 1
                    next_line = lines[i]
                    hostname = None
                    while not salt_re.match(next_line):
                        if hostname_re.search(next_line):
                            hostname = next_line.split(':')[1].strip()
                        else :
                            line_each_node += '%s\n\r' % next_line
                        i += 1
                        try:
                            next_line = lines[i]
                        except IndexError:
                            break
                    callback(hostname, line_each_node, now)
                else:
                    i += 1
        else:
            logger.error('Cannot execute command %s ' % cmd)
            raise RuntimeError('Cannot execute command %s ' % cmd)

    def get_db_connection(self, in_memory=False):
        if in_memory:
            return sqlite3.connect(':memory:')
        else:
            return sqlite3.connect(PATH + '/' + self.uc + '.db')

    @staticmethod
    def build_parser():
        """
        Builds the argparser object
        :return: Configured argparse.ArgumentParser object
        """
        parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description='CBIS post installation check')

        parser.add_argument('-uc', '--uc_hostname',
                            required=True,
                            help='Undercloud hostname (sample rst-exp3-uc)')

        parser.add_argument('-o', '--output',
                            default='/tmp',
                            help='Output folder')

        parser.add_argument('-t', '--test', action='store_const', const=True,
                            help='Test Flag for dev mode')

        parser.add_argument('-tc', '--test_case', choices=[cls.__name__ for cls in BaseCheck.__subclasses__()],
                            help="Test case to be checked")

        return parser


def main(args=sys.argv[1:]):

    arg_parser = CheckEngine.build_parser()
    args = arg_parser.parse_args(args)

    uc = args.uc_hostname

    output_folder = args.output

    now = datetime.datetime.now()

    output_file = "%s/%s-post_install_check_%s.txt" % (output_folder, uc, now.strftime("%Y_%m_%d_%H_%M"))

    csv_file = "%s/%s-post_install_check_%s.csv" % (output_folder, uc, now.strftime("%Y_%m_%d_%H_%M"))

    test_case = args.test_case

    check_engine = CheckEngine(uc=uc, test_flag=args.test, output_file=output_file, output_csv_file=csv_file)
    if not test_case:
        check_engine.check_all()
    else:
        check_engine.check(test_case.split(','))

    logger.info('check complete, output locate on : %s, csv file on : %s' % (output_file, csv_file))


if __name__ == "__main__":
    exit(main(args=sys.argv[1:]))
