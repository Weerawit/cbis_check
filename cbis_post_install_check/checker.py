#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import print_function
import abc


class BaseCheck(object):
    def __init__(self, engine):
        self.engine = engine
        self.conn = None
        self.init_table()

    @abc.abstractmethod
    def init_table(self, conn):
        raise NotImplemented()

    @abc.abstractmethod
    def cmd(self):
        raise NotImplemented()

    @abc.abstractmethod
    def host_pattern(self):
        return '*'

    @abc.abstractmethod
    def call_back(self, hostname, data, timestamp):
        raise NotImplemented()

    def _collect(self):
        self.engine.run_xargs(host_pattern=self.host_pattern(), cmd=self.cmd(), callback=self.call_back)

    @abc.abstractmethod
    def summary(self):
        raise NotImplemented()

    def check(self):
        self._collect()
        return self.summary()


class NTP(BaseCheck):
    """Run timedatectl to verify NTP setting"""

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS ntp (host text, key text, value text)')
        self.conn.execute('DELETE FROM ntp')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'timedatectl'

    def host_pattern(self):
        return '*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                try:
                    key, value = line.split(':')
                    self.conn.execute('insert into ntp (host, key, value) values (?, ?, ?)',
                                 (hostname, key.strip(), value.strip()))
                    self.conn.commit()
                except ValueError:
                    pass

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from ntp "
                                     "where key like 'NTP%' and value != 'yes' order by host"):
            output += '%s,NOK\n\r' % row[0]

        return output


class DashboardTimezone(BaseCheck):
    """Check TIME_ZONE /etc/openstack-dashboard/local_settings in all controller,
    should be Asia/Bangkok """
    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS timezone (host text, key text, value text)')
        self.conn.execute('DELETE FROM timezone')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo grep TIME_ZONE /etc/openstack-dashboard/local_settings'

    def host_pattern(self):
        return 'controller-*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                try:
                    key, value = line.split('=')
                    self.conn.execute('insert into timezone (host, key, value) values (?, ?, ?)',
                                 (hostname, key.strip(), value.strip()))
                    self.conn.commit()
                except ValueError:
                    pass

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from timezone "
                                     "where value not like '%Asia/Bangkok%' order by host"):
            output += '%s,NOK\n\r' % row[0]

        return output


class BMCColdRedundency(BaseCheck):
    """Check Intel_pstate cold redundancy should be disabled by
    run ipmitool raw 0x30 0xc3 second byte should be 00 """
    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS bmc (host text, value text)')
        self.conn.execute('DELETE FROM bmc')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo ipmitool raw 0x30 0xc3'

    def host_pattern(self):
        return '*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                try:
                    values = line.split()
                    self.conn.execute('insert into bmc (host, value) values (?,?)',
                                 (hostname, values[1].strip()))
                    self.conn.commit()
                except IndexError:
                    pass

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from bmc where value != '00' order by host"):
            output += '%s,NOK\n\r' % row[0]

        return output


class APCIPadDisable(BaseCheck):
    """Check acpi_pad should be disable (acpi_pad.disable=1)
    by run sudo cat /proc/cmdline """
    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS apcipad (host text, value text)')
        self.conn.execute('DELETE FROM apcipad')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo cat /proc/cmdline'

    def host_pattern(self):
        return '*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                try:
                    self.conn.execute('insert into apcipad (host, value) values (?,?)',
                                 (hostname, line.strip()))
                    self.conn.commit()
                except IndexError:
                    pass

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from apcipad "
                                     "where value not like '%acpi_pad.disable=1%' order by host"):
            output += '%s,NOK\n\r' % row[0]

        return output


class SriovHugePage(BaseCheck):
    """Check huge page setting for sriov node (vf_num > 0)
    by run grep Huge /proc/meminfo """
    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS sriov (host text, key text, value text)')
        self.conn.execute('DELETE FROM sriov')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'grep config_sriov.py /usr/lib/systemd/system/sriov.service;grep Huge /proc/meminfo'

    def host_pattern(self):
        return 'compute-*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                if '--vf_num' in line:
                    values = line.split('--vf_num')
                    if values[1].strip() == '0':
                        break
                else:
                    key, value = line.split(':')
                    self.conn.execute('insert into sriov (host, key, value) values (?, ?, ?)',
                                      (hostname, key.strip(), value.strip()))
                    self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from sriov "
                                     "where key = 'Hugepagesize' and value not like '%1048576 kB%' order by host"):
            output += '%s,NOK\n\r' % row[0]

        return output


class RabbitMqBacklog(BaseCheck):
    """Check rabbitmq 's backlog should be 4096 on controller
    by run rabbitmqctl environment | grep backlog
     """
    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS rabbitmqctl (host text, value text)')
        self.conn.execute('DELETE FROM rabbitmqctl')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo rabbitmqctl environment | grep backlog'

    def host_pattern(self):
        return 'controller-*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                if 'backlog' in line:
                    values = line.split(',')
                    self.conn.execute('insert into rabbitmqctl (host, value) values (?, ?)',
                                      (hostname, values[1].replace('}', '')))
                    self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from rabbitmqctl "
                                     "where value not like '%4096%' order by host"):
            output += '%s,NOK\n\r' % row[0]

        return output


class VitrageHostEvacuation(BaseCheck):
    """Check vitrage's configuration on controller for enable_host_evacuate should be False
    """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS vitrage (host text, key text, value text)')
        self.conn.execute('DELETE FROM vitrage')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'grep enable_host_evacuate /etc/vitrage/vitrage.conf'

    def host_pattern(self):
        return 'controller-*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                key, value = line.split('=')
                self.conn.execute('insert into vitrage (host, key, value) values (?, ?, ?)',
                                  (hostname, key.strip(), value.strip()))
                self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from vitrage "
                                     "where key = 'enable_host_evacuate' and lower(value) != 'false' order by host"):
            output += '%s,NOK\n\r' % row[0]

        return output


class NovaDefaultConfiguration(BaseCheck):
    """Check nova's configuration for default section on
    controller scheduler_max_attempts and scheduler_default_filters

    scheduler_max_attempts = 100
    scheduler_default_filters = ServerGroupAffinityFilter,ServerGroupAntiAffinityFilter,
                                AggregateInstanceExtraSpecsFilter,AvailabilityZoneFilter,RetryFilter,
                                NUMATopologyFilter,PciPassthroughFilter,RamFilter,ComputeFilter,
                                ImagePropertiesFilter,CoreFilter

    """

    scheduler_default_filters = 'ServerGroupAffinityFilter,ServerGroupAntiAffinityFilter,' \
                                'AggregateInstanceExtraSpecsFilter,AvailabilityZoneFilter,RetryFilter,' \
                                'NUMATopologyFilter,PciPassthroughFilter,RamFilter,ComputeFilter,' \
                                'ImagePropertiesFilter,CoreFilter'

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS nova_default (host text, key text, value text)')
        self.conn.execute('DELETE FROM nova_default')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo crudini --format=ini --get  /etc/nova/nova.conf DEFAULT'

    def host_pattern(self):
        return 'controller-*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                try:
                    key, value = line.split('=')
                    self.conn.execute('insert into nova_default (host, key, value) values (?, ?, ?)',
                                      (hostname, key.strip(), value.strip()))
                    self.conn.commit()
                except ValueError:
                    pass

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from nova_default "
                                     "where (key = 'scheduler_max_attempts' and value != '100') or "
                                     "(key ='scheduler_default_filters' and value != ? ) order by host",
                                     (self.scheduler_default_filters,)):
            output += '%s,NOK\n\r' % row[0]

        return output


class SriovZombieScript(BaseCheck):
    """Check zombie script should be installed on sriov nodes by run ls /zabbix_utils/zombie_vf.sh
    """
    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS sriov_zombie (host text, key text, value text)')
        self.conn.execute('DELETE FROM sriov_zombie')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'grep config_sriov.py /usr/lib/systemd/system/sriov.service;ls /zabbix_utils/zombie_vf.sh 2>&1'

    def host_pattern(self):
        return 'compute-*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                if '--vf_num' in line:
                    values = line.split('--vf_num')
                    if values[1].strip() == '0':
                        break
                elif 'No such file or directory' in line:
                    self.conn.execute('insert into sriov_zombie (host, key, value) values (?, ?, ?)',
                                      (hostname, None, None))
                    self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from sriov_zombie "
                                     "order by host"):
            output += '%s,NOK\n\r' % row[0]

        return output


class ZabbixConfig(BaseCheck):
    """Check zabbix's configuration on controller (StartPingers=3, StartPollers >= 15
    in /etc/zabbix/zabbix_server.conf
    """
    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS zabbix_conf (host text, key text, value text)')
        self.conn.execute('DELETE FROM zabbix_conf')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo cat /etc/zabbix/zabbix_server.conf'

    def host_pattern(self):
        return 'controller-*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                try:
                    key, value = line.split('=')
                    self.conn.execute('insert into zabbix_conf (host, key, value) values (?, ?, ?)',
                                      (hostname, key.strip(), value.strip()))
                    self.conn.commit()
                except ValueError:
                    pass

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from zabbix_conf "
                                     "where (key = 'StartPingers' and value != '3') "
                                     "or (key = 'StartPollers' and value < '15') "
                                     "order by host"):
            output += '%s,NOK\n\r' % row[0]

        return output


class NovaLibvirtConfiguration(BaseCheck):
    """Check nova's configuration for disk_cachemodes on compute
     disk_cachemodes = network=writeback
     """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS nova_libvirt (host text, key text, value text)')
        self.conn.execute('DELETE FROM nova_libvirt')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo crudini --get --format=ini /etc/nova/nova.conf libvirt disk_cachemodes 2>&1'

    def host_pattern(self):
        return 'compute-*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                try:
                    if 'Parameter not found' in line:
                        self.conn.execute('insert into nova_libvirt (host, key, value) values (?, ?, ?)',
                                      (hostname, 'disk_cachemodes', ''))
                        self.conn.commit()
                    elif ' = ' in line:
                        key, value = line.split(' = ')
                        self.conn.execute('insert into nova_libvirt (host, key, value) values (?, ?, ?)',
                                          (hostname, key.strip(), value.strip()))
                        self.conn.commit()

                except ValueError:
                    pass

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from nova_libvirt "
                                     "where (key = 'disk_cachemodes' and value != 'network=writeback')"
                                     "order by host",):
            output += '%s,NOK\n\r' % row[0]

        return output


class NovaQuotaConfiguration(BaseCheck):
    """Check nova's configuration for quota setting on controller (quota_server_groups, quota_server_group_members)

    quota_server_groups = 100
    quota_server_group_members = 60
    """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS nova_default (host text, key text, value text)')
        self.conn.execute('DELETE FROM nova_default')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo crudini --get --format=ini /etc/nova/nova.conf DEFAULT quota_server_groups 2>&1;' \
                   'sudo crudini --get --format=ini /etc/nova/nova.conf DEFAULT quota_server_group_members 2>&1'

    def host_pattern(self):
        return 'controller-*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                try:
                    if 'Parameter not found: quota_server_group_members' in line:
                        self.conn.execute('insert into nova_default (host, key, value) values (?, ?, ?)',
                                      (hostname, 'quota_server_group_members', ''))
                        self.conn.commit()
                    elif 'Parameter not found: quota_server_groups' in line:
                        self.conn.execute('insert into nova_default (host, key, value) values (?, ?, ?)',
                                      (hostname, 'quota_server_groups', ''))
                        self.conn.commit()
                    elif ' = ' in line:
                        key, value = line.split(' = ')
                        self.conn.execute('insert into nova_default (host, key, value) values (?, ?, ?)',
                                          (hostname, key.strip(), value.strip()))
                        self.conn.commit()

                except ValueError:
                    pass

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from nova_default "
                                     "where (key = 'quota_server_group_members' and value != '60') or "
                                     "(key ='quota_server_groups' and value != '100' ) order by host"):
            output += '%s,NOK\n\r' % row[0]

        return output


class CinderConfiguration(BaseCheck):
    """Check cinder's configuration for scheduler_max_attempts setting on controller
    scheduler_max_attempts = 100
    """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS cinder_default (host text, key text, value text)')
        self.conn.execute('DELETE FROM cinder_default')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo crudini --get --format=ini /etc/cinder/cinder.conf DEFAULT scheduler_max_attempts 2>&1'

    def host_pattern(self):
        return 'controller-*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                try:
                    if 'Parameter not found: scheduler_max_attempts' in line:
                        self.conn.execute('insert into cinder_default (host, key, value) values (?, ?, ?)',
                                      (hostname, 'scheduler_max_attempts', ''))
                        self.conn.commit()
                    elif ' = ' in line:
                        key, value = line.split(' = ')
                        self.conn.execute('insert into cinder_default (host, key, value) values (?, ?, ?)',
                                          (hostname, key.strip(), value.strip()))
                        self.conn.commit()

                except ValueError:
                    pass

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from cinder_default "
                                     "where (key = 'scheduler_max_attempts' and value != '100') order by host"):
            output += '%s,NOK\n\r' % row[0]

        return output


class UndercloudMTUConfig(BaseCheck):
    """Check MTU=9000 configuration in undercloud
    /etc/sysconfig/network-scripts/ifcfg-eth0
    /etc/sysconfig/network-scripts/ifcfg-eth1
    """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS undercloud_mtu (host text, key text, value text)')
        self.conn.execute('DELETE FROM undercloud_mtu')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'grep MTU /etc/sysconfig/network-scripts/ifcfg-eth*'

    def host_pattern(self):
        return 'undercloud'

    def call_back(self, hostname, data, timestamp):
        count = 2
        for line in data.splitlines():
            if line:
                try:
                    if '/etc/sysconfig/network-scripts/ifcfg-eth0' in line:
                        count = count - 1
                    elif '/etc/sysconfig/network-scripts/ifcfg-eth1' in line:
                        count = count - 1
                    elif '/etc/sysconfig/network-scripts/ifcfg-br-ctlplane' in line:
                        count = count - 1
                except ValueError:
                    pass

        if count > 0:
            self.conn.execute('insert into undercloud_mtu (host) values (?)',
                              (hostname,))
            self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from undercloud_mtu "):
            output += '%s,NOK\n\r' % row[0]

        return output


class UndercloudMTURuntime(BaseCheck):
    """Check MTU=9000 with ifconfig in undercloud
    ifconfig command
    """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS undercloud_mtu_runtime (host text, key text, value text)')
        self.conn.execute('DELETE FROM undercloud_mtu_runtime')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo ifconfig |grep 9000'

    def host_pattern(self):
        return 'undercloud'

    def call_back(self, hostname, data, timestamp):
        count = 3
        for line in data.splitlines():
            if line:
                try:
                    if 'eth0' in line:
                        count = count - 1
                    elif 'eth1' in line:
                        count = count - 1
                    elif 'br-ctlplane' in line:
                        count = count - 1
                except ValueError:
                    pass

        if count > 0:
            self.conn.execute('insert into undercloud_mtu_runtime (host) values (?)',
                              (hostname,))
            self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from undercloud_mtu_runtime "):
            output += '%s,NOK\n\r' % row[0]

        return output


class SriovTrustOn(BaseCheck):
    """Check VF trust setting should be on in SRIOV compute
    """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS sriov_trust_on (host text, key text, value text)')
        self.conn.execute('DELETE FROM sriov_trust_on')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'grep config_sriov.py /usr/lib/systemd/system/sriov.service;sudo ip link show |grep vf |grep "trust off"'

    def host_pattern(self):
        return 'compute-*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                try:
                    if line:
                        if '--vf_num' in line:
                            values = line.split('--vf_num')
                            if values[1].strip() == '0':
                                break
                        else:
                            self.conn.execute('insert into sriov_trust_on (host) values (?)',
                                              (hostname,))
                            self.conn.commit()
                            break

                except ValueError:
                    pass

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from sriov_trust_on "):
            output += '%s,NOK\n\r' % row[0]

        return output
