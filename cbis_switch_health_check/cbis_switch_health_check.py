#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import print_function

import argparse
import sys

import sqlite3
import logging.config
import datetime
from prettytable import PrettyTable
import pexpect
from checker import *


PATH = os.path.dirname(os.path.abspath(__file__))

logger = logging.getLogger(__name__)
logging.config.fileConfig(os.path.join(PATH, 'logging.ini'), disable_existing_loggers=False)


class CheckEngine(object):

    def __init__(self, switch_type, switch_ip, test_flag, output_file, output_csv_file, output_command_history_file,
                 output_logging_file):
        self.switch_ip = switch_ip
        self.switch_type = switch_type
        self.test_flag = test_flag
        self.output_file = output_file
        self.output_csv_file = output_csv_file
        self.output_command_history_file = output_command_history_file
        self.output_logging_file = output_logging_file
        self.username = 'nokia'
        self.password = 'nokia1234'

        self.__check_config = self.__setup()

    def __load_config(self, config_file):
        return [GenericCheck(line.split(',')[0].strip(), line.split(',')[1].strip()) if line.strip().split(',').__len__() > 1
                         else GenericCheck(line.strip()) for line in open(os.path.join(PATH, config_file))]

    def __setup(self):

        generic_check = self.__load_config('generic_check.txt')
        generic_check.extend([CPUStatus(), MemoryStatus(), CRCError(self), FECError(self)])

        spine_mgt = self.__load_config('spine_mgt_check.txt')
        spine_mgt.extend(generic_check)

        spine_nep = self.__load_config('spine_nep_check.txt')
        spine_nep.extend(generic_check)

        spine_exp = self.__load_config('spine_exp_check.txt')
        spine_exp.extend(generic_check)

        spine_fabric = self.__load_config('spine_fabric_check.txt')
        spine_fabric.extend(generic_check)

        spine_sec = self.__load_config('spine_sec_check.txt')
        spine_sec.extend(generic_check)

        border_leaf = self.__load_config('border_leaf_check.txt')
        border_leaf.extend(generic_check)

        return {'spine-mgt': spine_mgt,
               'spine-nep': spine_nep,
               'spine-exp': spine_exp,
               'spine-fabric': spine_fabric,
               'spine-sec': spine_sec,
               'border-leaf': border_leaf
               }

    def get_db_connection(self, in_memory=False):
        if in_memory:
            return sqlite3.connect(':memory:')
        else:
            return sqlite3.connect(PATH + '/' + self.switch_ip + '.db')

    def check_all(self):
        records = []
        now = datetime.datetime.now()
        ssh_cmd = 'ssh %s@%s' % (self.username, self.switch_ip)
        logger.info('Login to %s' % (ssh_cmd,))
        child = pexpect.spawn(ssh_cmd)
        i = child.expect([pexpect.TIMEOUT, '(yes/no)', '[Pp]assword: '])

        if i == 0:  # Timeout
            logger.error('ERROR!')
            logger.error('SSH could not login. Here is what SSH said:')
            logger.error(child.before, child.after)
            sys.exit(1)
        if i == 1:  # SSH does not have the public key. Just accept it.
            child.sendline('yes')
            child.expect('[Pp]assword: ')

        child.sendline(self.password)
        i = child.expect(['Permission denied', '#'])

        if i == 0:
            logger.info('Permission denied on host. Can\'t login')
            child.kill(0)
        elif i == 1:
            logger.info('Login OK.')
            #per switch_type
            with contextlib.closing(child):

                checker_list = self.__check_config.get(self.switch_type)

                for checker in checker_list:

                    if isinstance(checker, str):
                        checker = GenericCheck(checker)
                    elif isinstance(checker, tuple):
                        checker = GenericCheck(checker[0], checker[1])

                    cmd = checker.cmd()
                    logger.info('executing %s' % (cmd,))

                    child.sendline(cmd)
                    child.expect('#')

                    result = child.before

                    records.append(checker.call_back(data=result, timestamp=now))

                #get command history
                yesterday = now - datetime.timedelta(days=1)

                with open(self.output_command_history_file, 'wb') as f:
                    cmd = 'show command-history | grep "%s|%s" | no-more' % (now.strftime('%-m/%d'), yesterday.strftime('%-m/%d'))
                    child.sendline(cmd)
                    child.expect('#')
                    f.write(child.before)

                #get logging
                with open(self.output_logging_file, 'wb') as f:
                    cmd = 'show logging | grep "%s|%s" | no-more' % (now.strftime('%b %d'), yesterday.strftime('%b %d'))
                    child.sendline(cmd)
                    child.expect('#')
                    f.write(child.before)

        #result to output txt
        with open(self.output_file, 'wb') as f, open(self.output_csv_file, 'wb') as f_csv:
            table = PrettyTable(['description', 'status'])
            table.align["description"] = "l"

            for record in records:
                table.add_row(record)
                f_csv.write('%s,%s\n' % (record[0], record[1]))

            f.write('%s\n' % table)


    @staticmethod
    def build_parser():
        """
        Builds the argparser object
        :return: Configured argparse.ArgumentParser object
        """
        parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description='CBIS post installation check')

        parser.add_argument('-switch', '--switch_ip',
                            required=True,
                            help='Switch IP (sample 10.x.x.x)')

        parser.add_argument('-type', '--type',
                            required=True,
                            choices=['spine-mgt', 'spine-nep', 'spine-exp', 'spine-fabric', 'spine-sec', 'border-leaf'],
                            help='Type of switch')

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

    switch_ip = args.switch_ip

    type = args.type

    output_folder = args.output

    now = datetime.datetime.now()

    output_file = "%s/%s-%s-switch_health_check_%s.txt" % (output_folder, type, switch_ip, now.strftime("%Y_%m_%d_%H_%M"))

    csv_file = "%s/%s-%s-switch_health_check_%s.csv" % (output_folder, type, switch_ip, now.strftime("%Y_%m_%d_%H_%M"))

    history_file = "%s/%s-%s-command_history_%s.txt" % (output_folder, type, switch_ip, now.strftime("%Y_%m_%d_%H_%M"))

    logging_file = "%s/%s-%s-logging_%s.txt" % (output_folder, type, switch_ip, now.strftime("%Y_%m_%d_%H_%M"))

    test_case = args.test_case

    check_engine = CheckEngine(switch_ip=switch_ip, switch_type=type , test_flag=args.test,
                               output_file=output_file, output_csv_file=csv_file,
                               output_command_history_file=history_file, output_logging_file=logging_file)
    if not test_case:
        check_engine.check_all()
    else:
        check_engine.check(test_case.split(','))

    logger.info('check complete\n output locate on : %s\n csv file on : %s\n history_file on : %s\n logging_file on : %s' %
                (output_file, csv_file, history_file, logging_file))


if __name__ == "__main__":
    exit(main(args=sys.argv[1:]))
