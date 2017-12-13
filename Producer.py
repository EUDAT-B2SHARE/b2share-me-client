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

import logging
import time
import configuration

logging.basicConfig(filename=configuration.log_file_path, level=configuration.logging_level)


def producer(client, input_queue, notification_queue):

    logging.debug('producer starts')

    cont = True
    while cont:
        client.generate_record_seq(input_queue)

        logging.debug('producer input queue size: %d', input_queue.qsize())

        input_queue.join()

        if input_queue.qsize() > configuration.consumer_concurrency:
            time.sleep(5)

        cont = False

    logging.debug('producer quits, stops consumers')
    for i in range(configuration.consumer_concurrency):
        t = (0, 'STOP')
        input_queue.put(t)

    # read notifications from queue and send them
    notification_list = []
    while not notification_queue.empty():
        notification_list.append(notification_queue.get())
    if notification_list:
        client.send_notification(notification_list)

    logging.debug('producer exits')
