#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import print_function
import abc
import collections


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


class PCSStatus(BaseCheck):
    """Check pcs status for all controller """
    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS pcs_status (host text, key text, value text)')
        self.conn.execute('DELETE FROM pcs_status')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo pcs status'

    def host_pattern(self):
        return 'controller-*'

    def call_back(self, hostname, data, timestamp):
        clone_set = None
        for line in data.splitlines():
            if line:
                if 'Clone Set' in line:
                    clone_set = line.split(':')[1]
                    continue
                if 'offline' in line.lower() or 'stopped' in line.lower() or 'failed' in line.lower():
                    self.conn.execute('insert into pcs_status (host) values (?)',
                                      (hostname,))
                    self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from pcs_status "):
            output += '%s,NOK\n\r' % row[0]

        return output


class PCSClusterStatus(BaseCheck):
    """Check pcs cluster status for all controller """
    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS pcs_cluster (host text, key text, value text)')
        self.conn.execute('DELETE FROM pcs_cluster')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo pcs cluster status'

    def host_pattern(self):
        return 'controller-*'

    def call_back(self, hostname, data, timestamp):
        found_pcsd = False
        for line in data.splitlines():
            if line:
                if 'PCSD Status' in line:
                    found_pcsd = True
                    continue
                if 'Online' not in line and found_pcsd:
                    values = line.split(':')
                    self.conn.execute('insert into pcs_cluster (host) values (?)',
                                      (values[0],))
                    self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from pcs_cluster "):
            output += '%s,NOK\n\r' % row[0]

        return output


class CephHealth(BaseCheck):
    """Check ceph health  for all controller """
    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS ceph_health (host text, key text, value text)')
        self.conn.execute('DELETE FROM ceph_health')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo ceph health'

    def host_pattern(self):
        return 'controller-*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                if 'HEALTH_OK' in line:
                    continue
                else:
                    self.conn.execute('insert into ceph_health (host) values (?)',
                                      (hostname,))
                    self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from ceph_health "):
            output += '%s,NOK\n\r' % row[0]

        return output


class CephOSDTree(BaseCheck):
    """Check ceph osd tree  for all controller """
    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS ceph_osd_tree (host text, key text, value text)')
        self.conn.execute('DELETE FROM ceph_osd_tree')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo ceph osd tree'

    def host_pattern(self):
        return 'controller-*'

    def call_back(self, hostname, data, timestamp):
        storage_host = ''
        for line in data.splitlines():
            if line:
                if 'host' in line:
                    storage_host = line.split('host ')[1].strip()
                    continue
                if 'osd.' in line and 'up' not in line:
                    values = line.split()
                    self.conn.execute('insert into ceph_osd_tree (host, key) values (?, ?)',
                                      (storage_host, values[2].strip()))
                    self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from ceph_osd_tree "):
            output += '%s,NOK\n\r' % row[0]

        return output


class CephService(BaseCheck):
    """Check ceph's service  for all storage-node """
    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS ceph_service (host text, key text, value text)')
        self.conn.execute('DELETE FROM ceph_service')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo systemctl status ceph\*.service ceph\*.target |grep -v -e Loaded: -e PID -e CGroup -e └'

    def host_pattern(self):
        return 'cephstorage-*'

    def call_back(self, hostname, data, timestamp):
        service_name = ''
        for line in data.splitlines():
            if line:
                if 'ceph' in line:
                    service_name = line.split('-')[0].strip()
                    continue
                if 'Active:' in line and 'active' not in line:
                    self.conn.execute('insert into ceph_service (host) values (?)',
                                      (hostname,))
                    self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from ceph_service "):
            output += '%s,NOK\n\r' % row[0]

        return output




class CephOSDConfig(BaseCheck):
    """Check osd config on storage node
     osd_scrub_chunk_min = 5,
     osd_scrub_chunk_max = 5,
     osd_scrub_sleep = 0.1,
     osd_deep_scrub_stride = 1048576
     """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS ceph_osd_config (host text, key text, value text)')
        self.conn.execute('DELETE FROM ceph_osd_config')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return "for osdid in `sudo ls -1 /var/lib/ceph/osd/ | cut -d '-' -f2`; " \
                   "do sudo ceph -n osd.$osdid --show-config | " \
                   "grep -E \"(scrub_chunk|deep_scrub_stride|osd_scrub_sleep)\" ; done"

    def host_pattern(self):
        return 'cephstorage-*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                try:
                    key, value = line.split(' = ')
                    self.conn.execute('insert into ceph_osd_config (host, key, value) values (?, ?, ?)',
                                      (hostname, key.strip(), value.strip()))
                    self.conn.commit()

                except ValueError:
                    pass

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from ceph_osd_config "
                                     "where (key = 'osd_scrub_chunk_min' and value != '5') or "
                                     "(key = 'osd_scrub_chunk_max' and value != '5') or "
                                     "(key = 'osd_scrub_sleep' and value != '0.1') or "
                                     "(key = 'osd_deep_scrub_stride' and value != '1048576')"
                                     "order by host",):
            output += '%s,NOK\n\r' % row[0]

        return output


class NTPStatum(BaseCheck):
    """Check ntpq -p should see 3 ntp server in all controller
     """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS ntp_statum (host text, key text, value text)')
        self.conn.execute('DELETE FROM ntp_statum')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return "sudo ntpq -p"

    def host_pattern(self):
        return 'controller-*'

    def call_back(self, hostname, data, timestamp):
        count = 0
        for line in data.splitlines():
            if line:
                if 'refid' in line or '==' in line:
                    continue
                else:
                    count += 1

        self.conn.execute('insert into ntp_statum (host, value) values (?, ?)',
                          (hostname, str(count)))
        self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from ntp_statum "
                                     "where value != '3' "
                                     "order by host",):
            output += '%s,NOK\n\r' % row[0]

        return output


class NTPStat(BaseCheck):
    """Check ntpstat in all controller node, should be synchronized
     """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS ntp_stat (host text, key text, value text)')
        self.conn.execute('DELETE FROM ntp_stat')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return "sudo ntpstat"

    def host_pattern(self):
        return 'controller-*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                if 'unsynchronised' in line or 'Unable to talk to NTP daemon.' in line:
                    self.conn.execute('insert into ntp_stat (host) values (?)',
                                      (hostname, ))
                    self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from ntp_stat "
                                     "order by host",):
            output += '%s,NOK\n\r' % row[0]

        return output


class NoveServiceList(BaseCheck):
    """Check nova service-list on overcloud
     """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS nova_service_list (host text, key text, value text)')
        self.conn.execute('DELETE FROM nova_service_list')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return "source /home/stack/overcloudrc; nova service-list"

    def host_pattern(self):
        return 'undercloud'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                if '+' in line or 'Binary' in line:
                    continue
                else:
                    values = line.split('|')
                    if 'up' not in values[6]:

                        self.conn.execute('insert into nova_service_list (host) values (?)',
                                          (values[3].strip(), ))
                        self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from nova_service_list "
                                     "order by host",):
            output += '%s,NOK\n\r' % row[0]

        return output


class NovaList(BaseCheck):
    """Check nova list on overcloud
    nova list --all --fields host,name,status,power_state
     """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS nova_list (host text, key text, value text)')
        self.conn.execute('DELETE FROM nova_list')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return "source /home/stack/overcloudrc; nova list --all --fields host,name,status,power_state"

    def host_pattern(self):
        return 'undercloud'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                if '+' in line or 'ID' in line:
                    continue
                else:
                    values = line.split('|')
                    if 'ACTIVE' not in values[4] or 'Running' not in values[5]:

                        self.conn.execute('insert into nova_list (host) values (?)',
                                          (values[3].strip(), ))
                        self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from nova_list "
                                     "order by host",):
            output += '%s,NOK\n\r' % row[0]

        return output


class NeutronAgentList(BaseCheck):
    """Check neutron agent-list on overcloud
     """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS neutron_agent_list (host text, key text, value text)')
        self.conn.execute('DELETE FROM neutron_agent_list')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return "source /home/stack/overcloudrc; neutron agent-list"

    def host_pattern(self):
        return 'undercloud'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                if '+' in line or 'agent_type' in line:
                    continue
                else:
                    values = line.split('|')
                    if ':-)' not in values[4]:

                        self.conn.execute('insert into neutron_agent_list (host) values (?)',
                                          (values[3].strip(),))
                        self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from neutron_agent_list "
                                     "order by host", ):
            output += '%s,NOK\n\r' % row[0]

        return output


class CinderServiceList(BaseCheck):
    """Check cinder service-lsit on overcloud
     """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS cinder_service_list (host text, key text, value text)')
        self.conn.execute('DELETE FROM cinder_service_list')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return "source /home/stack/overcloudrc; cinder service-list"

    def host_pattern(self):
        return 'undercloud'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                if '+' in line or 'Binary' in line:
                    continue
                else:
                    values = line.split('|')
                    if 'up' not in values[5]:
                        self.conn.execute('insert into cinder_service_list (host) values (?)',
                                          (values[2].strip(),))
                        self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from cinder_service_list "
                                     "order by host", ):
            output += '%s,NOK\n\r' % row[0]

        return output


class SriovNumberOfVF(BaseCheck):
    """Check number of vf in compute node, should be 380 (4*95)
     """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS sriov_number_vf (host text, key text, value text)')
        self.conn.execute('DELETE FROM sriov_number_vf')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return "grep config_sriov.py /usr/lib/systemd/system/sriov.service; sudo ip l |grep vf |wc -l"

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
                    self.conn.execute('insert into sriov_number_vf (host, value) values (?, ?)',
                                  (hostname, line.strip()))
                    self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from sriov_number_vf "
                                     "where value != '380' "
                                     "order by host", ):
            output += '%s,NOK\n\r' % row[0]

        return output


class IPAEns6F0andEns6F1Interface(BaseCheck):
    """Check sudo ip a |grep -E ens6f0|ens6f1 should not have DOWN Interface
     """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS ipa_ens6 (host text, key text, value text)')
        self.conn.execute('DELETE FROM ipa_ens6')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo ip a |grep -E "ens6f0|ens6f1" '

    def host_pattern(self):
        return 'compute-*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                if 'UP' not in line:
                    self.conn.execute('insert into ipa_ens6 (host, value) values (?, ?)',
                                  (hostname, line.strip()))
                    self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from ipa_ens6 "
                                     "order by host", ):
            output += '%s,NOK\n\r' % row[0]

        return output


class OvsvsctlGetFailMode(BaseCheck):
    """Check ovs-vsctl get-fail-mode br-ex should be secure in all compute
     """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS get_fail_mode (host text, key text, value text)')
        self.conn.execute('DELETE FROM get_fail_mode')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo ovs-vsctl get-fail-mode br-ex '

    def host_pattern(self):
        return 'compute-*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                if 'secure' not in line:
                    self.conn.execute('insert into get_fail_mode (host, value) values (?, ?)',
                                  (hostname, line.strip()))
                    self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from get_fail_mode "
                                     "order by host", ):
            output += '%s,NOK\n\r' % row[0]

        return output


class OvsofctlDumpflow(BaseCheck):
    """Check ovs-ofctl dump-flows br-ex should not contain cookie 0x0 in all compute
     """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS ofctl_dump_flow (host text, key text, value text)')
        self.conn.execute('DELETE FROM ofctl_dump_flow')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo ovs-ofctl dump-flows br-ex '

    def host_pattern(self):
        return 'compute-*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line or 'NXST_FLOW' not in line:
                if 'cookie=0x0,' in line:
                    self.conn.execute('insert into ofctl_dump_flow (host, value) values (?, ?)',
                                  (hostname, line.strip()))
                    self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from ofctl_dump_flow "
                                     "order by host", ):
            output += '%s,NOK\n\r' % row[0]

        return output


class CpuFrequency(BaseCheck):
    """Check all cpu frequency  cpupower frequency-info |grep current CPU
    CPU should more than 1 GHz
     """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS cpu_frequency (host text, key text, value text)')
        self.conn.execute('DELETE FROM cpu_frequency')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo cpupower frequency-info |grep "current CPU"'

    def host_pattern(self):
        return '*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                if 'current CPU frequency:' in line:
                    values = line.split(':')
                    self.conn.execute('insert into cpu_frequency (host, value) values (?, ?)',
                                  (hostname, values[1]))
                    self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select host, value from cpu_frequency "
                                     "where value not like '%2%Ghz%' and value not like '%3%Ghz%' "
                                     "and value not like '%1%Ghz%' "
                                     "order by host", ):
            output += '%s,NOK\n\r' % row[0]

        return output


class HugePageSetting(BaseCheck):
    """Check all hugepage cat /proc/meminfo |grep -i hugepagesize in all node
    compute node should have 1048576 Kb (Applicable for sriov pod)
     """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS hugepage (host text, key text, value text)')
        self.conn.execute('DELETE FROM hugepage')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'grep config_sriov.py /usr/lib/systemd/system/sriov.service 2>&1; sudo cat /proc/meminfo |grep -i hugepagesize'

    def host_pattern(self):
        return '*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                if '--vf_num' in line:
                    values = line.split('--vf_num')
                    if values[1].strip() == '0':
                        break
                elif 'No such file or directory' in line:
                    break
                else:
                    try:
                        key, value = line.split(':')
                        self.conn.execute('insert into hugepage (host, key, value) values (?, ?, ?)',
                                          (hostname, key.strip(), value.strip()))
                        self.conn.commit()

                    except ValueError:
                        pass

    def summary(self):
        output = ''
        for row in self.conn.execute("select host, value from hugepage "
                                     "where "
                                     "((host like '%controller%' or host like '%cephstorage%') and value != '2048 kB') "
                                     "or (host like '%compute%' and value != '1048576 kB' )"
                                     "order by host", ):
            output += '%s,NOK\n\r' % (row[0] + " (" + row[1] + ")")

        return output


class NovaLibvirtConfiguration(BaseCheck):
    """Check nova's configuration for disk_cachemodes on compute
     disk_cachemodes = network=writeback
     sync_power_state_interval = -1
     """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS nova_libvirt (host text, key text, value text)')
        self.conn.execute('DELETE FROM nova_libvirt')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return 'sudo crudini --get --format=ini /etc/nova/nova.conf libvirt disk_cachemodes 2>&1' \
                   ';sudo crudini --get --format=ini /etc/nova/nova.conf libvirt sync_power_state_interval 2>&1'

    def host_pattern(self):
        return 'compute-*'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                try:
                    if 'Parameter not found' in line:
                        values = line.split(':')
                        self.conn.execute('insert into nova_libvirt (host, key, value) values (?, ?, ?)',
                                      (hostname, values[1].strip(), ''))
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
                                     "where (key = 'disk_cachemodes' and value != 'network=writeback') or "
                                     "(key = 'sync_power_state_interval' and value != '-1')"
                                     "order by host",):
            output += '%s,NOK\n\r' % row[0]

        return output


class IronicNodelist(BaseCheck):
    """Check ironic node-list on undercloud
    Power State should be power-on
    Provisioning State should be active
    Maintenance should be False
     """

    def init_table(self):
        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS ironic_node_list (host text, key text, value text)')
        self.conn.execute('DELETE FROM ironic_node_list')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return "source /home/stack/stackrc; ironic node-list"

    def host_pattern(self):
        return 'undercloud'

    def call_back(self, hostname, data, timestamp):
        for line in data.splitlines():
            if line:
                if '+' in line or 'UUID' in line:
                    continue
                else:
                    values = line.split('|')
                    if 'power on' not in values[4] or 'active' not in values[5] or 'False' not in values[6]:

                        self.conn.execute('insert into ironic_node_list (host) values (?)',
                                          (values[2].strip(), ))
                        self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from ironic_node_list "
                                     "order by host",):
            output += '%s,NOK\n\r' % row[0]

        return output


class EthToolCheck(BaseCheck):
    """Check ethtool -S on ens1f0,ens1f1,ens3f0,ens3f1,ens6f0,ens6f1 with key rx_discards_phy

     """

    def __init__(self, engine):
        self.old_data = collections.defaultdict(dict)
        super(EthToolCheck, self).__init__(engine)

    def init_table(self):

        self.conn = self.engine.get_db_connection()
        self.conn.execute('CREATE TABLE IF NOT EXISTS ethtools (host text, key text, value text, is_change text)')
        for row in self.conn.execute('select host, key, value from ethtools'):
            self.old_data[row[0]][row[1]] = row[2]
        self.conn.execute('DELETE FROM ethtools')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            interface_list = ['ens1f0', 'ens1f1', 'ens3f0', 'ens3f1', 'ens6f0', 'ens6f1']
            command = ''
            for interface in interface_list:
                command += 'echo %s;/usr/sbin/ethtool -S %s | grep rx_discards_phy;' % (interface, interface)

            return command

    def host_pattern(self):
        return 'compute-*'

    def call_back(self, hostname, data, timestamp):

        current_interface = ''
        for line in data.splitlines():
            if line:
                if line.startswith('ens'):
                    current_interface = line.strip()
                    continue
                else:
                    key, value = line.split(':')

                    key = '{0}_{1}'.format(current_interface, key.strip())
                    is_change = 'N'
                    try:
                        if self.old_data.get(hostname).get(key) != value.strip():
                            is_change = 'Y'
                    except AttributeError:
                        pass

                    self.conn.execute('insert into ethtools (host, key, value, is_change) values (?, ?, ?, ?)', (hostname, key.strip(), value.strip(), is_change))
                    self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from ethtools where is_change ='Y' "
                                     "order by host",):
            output += '%s,NOK\n\r' % row[0]

        return output


class StorageSSDCheck(BaseCheck):
    """Check /opt/MegaRAID/storcli/storcli64 /c0 show should have 2 SSD

     """
    def init_table(self):

        self.conn = self.engine.get_db_connection(in_memory=True)
        self.conn.execute('CREATE TABLE IF NOT EXISTS storage_ssd (host text, key text, value text)')
        self.conn.execute('DELETE FROM storage_ssd')

    def cmd(self):
        if self.engine.test_flag:
            return 'cat /Users/weerawit/Downloads/compute.log'
        else:
            return "sudo /opt/MegaRAID/storcli/storcli64 /c0 show | grep SSD"

    def host_pattern(self):
        return 'cephstorage'

    def call_back(self, hostname, data, timestamp):
        count = 0
        for line in data.splitlines():
            if line:
                count += 1

        if count < 2:
            self.conn.execute('insert into storage_ssd (host) values (?)',
                              (hostname.strip(),))
            self.conn.commit()

    def summary(self):
        output = ''
        for row in self.conn.execute("select distinct host from storage_ssd "
                                     "order by host",):
            output += '%s,NOK\n\r' % row[0]

        return output
