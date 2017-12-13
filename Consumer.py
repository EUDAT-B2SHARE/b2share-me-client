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

import os
import logging
import configuration

logging.basicConfig(filename=configuration.log_file_path, level=configuration.logging_level)


def consumer(client, input_queue, notification_queue):
    c_pid = os.getpid()
    logging.debug('%d consumer starts', c_pid)

    while True:
        # get tuple (status, draft id)
        t = input_queue.get()
        status = t[0]
        logging.debug('%d consumer status: %d', c_pid, status)

        if status == 0:
            logging.debug('%d consumer stops', c_pid)
            input_queue.task_done()
            break

        if len(t[1]) > 5 and t[0] == 1:
            draft_id = t[1]
            logging.debug('%d consumer, draft %s', c_pid, draft_id)
            draft = client.get_draft(draft_id)

            file_path = client.get_draft_file(draft)
            if file_path is None:
                logging.warning('%d consumer, moving on to next record in the queue', c_pid)
                input_queue.task_done()
                continue

            logging.debug('%d consumer, draft %s : %s', c_pid, draft_id, file_path)

            json_patch = client.community_metadata(draft, file_path)
            url = client.update_draft(draft, json_patch)
            logging.debug('%d consumer, URL: %s', c_pid, url)

            if url is not None:
                notification_queue.put(url)

        input_queue.task_done()

    logging.debug('%d consumer exits', c_pid)
