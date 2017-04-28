# Copyright (c) 2017 UFCG-LSD.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import paramiko
import time

from application_manager.openstack import connector as os_connector
from application_manager.plugins import base
#from application_manager.utils import monitor
#from application_manager.utils import scaler
from application_manager.utils.logger import Log

from paramiko.ssh_exception import *


LOG = Log("OpenStackGenericPlugin", "openstack_generic_plugin.log")


class OpenStackGenericProvider(base.PluginInterface):

    def get_title(self):
        return 'OpenStack Generic Plugin'

    def get_description(self):
        return 'Plugin that allows utilization of generic OpenStack to run jobs'

    def to_dict(self):
        return {
            'name': self.name,
            'title': self.get_title(),
            'description': self.get_description(),
        }

    def execute(self, data, user, password, project_id, auth_ip, domain,
                public_key, net_id):

        connector = os_connector.OpenStackConnector(LOG)
        nova = connector.get_nova_client(user, password, project_id, auth_ip,
                                         domain)
        image_id = data['image_id']
        flavor_id = data['flavor_id']
        command = data['command']
        cluster_size = data['cluster_size']
        # Change to accept keypair name
        instances = self._create_instances(nova, connector, image_id,
                                           flavor_id, public_key, cluster_size)

        instances_nets = []
        for instance_id in instances:
            instance_status = connector.get_instance_status(nova, instance_id)
            while instance_status != 'ACTIVE':
                instance_status = connector.get_instance_status(nova,
                                                                instance_id)

            instance_ips = connector.get_instance_networks(nova, instance_id)
            instances_nets.append(instance_ips)
            time.sleep(30)

        conns = []
        for instance_net in instances_nets:
            for net_ip_list in instance_net.values():
                for ip in net_ip_list:

                    attempts = 2
                    while attempts != -1:
                        try:
                            instance_conn = self._get_ssh_connection(ip)
                            conns.append(instance_conn)
                            attempts = -1
                        except NoValidConnectionsError:
                            print "Fail to connect "
                            attempts -= 1
                            time.sleep(30)


        for conn in conns:
            # Check if exec_command will work without blocking execution
            conn.exec_command(command)

            # monitor.start_monitor(spark_app_id, plugin_app, info_plugin,
            #                       collect_period)
            # scaler.start_scaler(spark_app_id, scaler_plugin, actuator,
            #                     metric_source, workers_id, check_interval,
            #                     trigger_down, trigger_up, min_cap, max_cap,
            #                     actuation_size, metric_rounding)

        application_running = True
        while application_running:
            status_instances = []
            for instance_id in instances:
                status = connector.get_instance_status(nova, instance_id)
                status_instances.append(status)

            print status_instances

            if self._instances_down(status_instances):
                application_running = False
            else:
                instance_status = []



        print "Application Finished"
        #self._remove_instances(nova, connector, instances)



    def _create_instances(self, nova, connector, image_id, flavor_id,
                          public_key, count):
        instances = []
        for i in range(count):
            instance = connector.create_instance(nova, image_id, flavor_id,
                                                 public_key)
            instances.append(instance)

        return instances

    def _get_ssh_connection(self, ip):
        keypair = paramiko.RSAKey.from_private_key_file('/home/iurygregory/.ssh/cloud.key')
        conn = paramiko.SSHClient()
        conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        conn.connect(hostname=ip, username="ubuntu", pkey=keypair)
        return conn

    def _remove_instances(self, nova, connector, instances):
        for instance_id in instances:
            connector.remove_instance(nova, instance_id)

    def _instances_down(self, status):
        print  self._all_same(status)
        print status[-1] == 'SHUTOFF'
        return self._all_same(status) and status[-1] == 'SHUTOFF'

    def _all_same(items):
        return all(x == items[-1] for x in items)
