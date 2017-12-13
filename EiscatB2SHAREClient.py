# Copyright (c) 2017 CSC - IT Center for Science Ltd.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from B2SHAREClient import B2SHAREClient
import Consumer
import Producer
from multiprocessing import Process, JoinableQueue, Queue
import sys
import logging
import h5py
import jsonpatch
import configuration

logging.basicConfig(filename=configuration.log_file_path, level=configuration.logging_level)


class EiscatB2SHAREClient(B2SHAREClient):

    def __init__(self, community, token, b2share_url):
        super().__init__(community, token, b2share_url)

    def community_metadata(self, draft, file_path):
        f = h5py.File(file_path, 'r')

        metadata = {}
        try:
            metadata_group = f['Metadata']
            experiment_parameters = {}
            for (name, obj) in metadata_group.items():
                if isinstance(obj, h5py.Dataset):
                    if name == "Experiment Parameters":
                        for t in obj.value:
                            # logging.debug('Experiment parameters: %s : %s', t[0], t[1])
                            experiment_parameters[t[0]] = t[1]

            metadata.update(experiment_parameters)
            # TODO: check the localization of scandinavian characters

        except Exception as inst:
            logging.warning('Exception: %s', inst)
            f.close()
            return jsonpatch.JsonPatch([])

        f.close()

        logging.debug('draft %s: metadata: %s', draft['id'], metadata)
        # assumes B2SHARE v2.0.1, there should be only one community specific id
        # community_specific_id = next(iter(draft['metadata']['community_specific']))
        community_specific_id = configuration.community_specific

        json_patch_list = []

        #community_specific_json = {"community_specific": {}}
        #json_patch = {"op": "add", "path": "/", "value": community_specific_json}
        #json_patch_list.append(json_patch)

        #community_specific_json = { community_specific_id : {} }
        #json_patch = {"op": "add", "path": "/community_specific", "value": community_specific_json}
        #json_patch_list.append(json_patch)

        # https://trng-b2share.eudat.eu/communities/EISCAT
        map_keys = {'kindat':'kindat', 'instrument':'instrument', 'start time':'start_time', 'end time': 'end_time',
                    'status description':'status','kind of data file':'kind_of_data_file','instrument latitude':'latitude',
                    'instrument longitude':'longitude', 'instrument altitude':'altitude'}

        for k in metadata.keys():
                mapped_key = None
                try:
                    mapped_key = map_keys[k.decode('utf-8')]
                except KeyError as e:
                    logging.warning('draft %s: metadata includes unknown key "%s" %s', draft['id'], k, k.decode('utf-8'))

                if mapped_key:
                    json_patch = {"op": "add", "path": "/community_specific/" + community_specific_id + "/"+mapped_key.replace(" ", "_"),
                              "value": metadata[k].decode('utf-8')}
                    json_patch_list.append(json_patch)

        # json_patch = {"op": "add","path": "/community_specific/" + community_specific_id + "/publication_state", "value": "submitted"}
        # json_patch_list.append(json_patch)

        patch = jsonpatch.JsonPatch(json_patch_list).to_string()
        logging.debug('draft %s: patch: %s', draft['id'], patch)

        return patch


def main():
    try:
        eiscat_b2share_client = EiscatB2SHAREClient(configuration.community, configuration.token,
                                                     configuration.b2share_url)
    except Exception as e:
        logging.debug('B2SHARE client exception: %s', e)
        sys.exit()

    number_of_processes = configuration.consumer_concurrency
    task_queue = JoinableQueue()
    notification_queue = Queue()

    Process(target=Producer.producer, args=(eiscat_b2share_client, task_queue, notification_queue,)).start()

    for i in range(number_of_processes):
        try:
            Process(target=Consumer.consumer, args=(eiscat_b2share_client, task_queue, notification_queue,)).start()
        except Exception as e:
            logging.debug('consumer exception %s', e)


if __name__ == '__main__':
    main()
