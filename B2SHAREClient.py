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

import requests
import os
import errno
import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import urlparse
from datetime import datetime
from os.path import basename

# import configuration
from configparser import SafeConfigParser


configuration=SafeConfigParser()
configuration.read('/usr/local/etc/eudatL2.conf')

logging.basicConfig(filename=configuration.get('Log','log_file_path'), level=eval(configuration.get('Log','logging_level')))


class B2SHAREClient(object):

    def __init__(self, community_id=None, token=None, url=None):

        self.cert_verify = False
        requests.packages.urllib3.disable_warnings()

        if url is not None:
            self.url = url
        else:
            raise Exception("B2SHARE URL is required!")

        if token is not None:
                self.token = token
        else:
            raise Exception("Authorization token is required!")

        if community_id is not None:
            self.community_id = community_id
            url = self.url + "/api/communities/" + self.community_id + "/schemas/last?access_token=" + self.token
            r = requests.get(url, verify=self.cert_verify)
            if r.status_code is not 200:
                raise Exception("Check configuration parameters. Connection failed to", url)
        else:
            raise Exception("Community id is required!")

    def get_records(self):
        url = self.url + "/api/records/?q=community:" + self.community_id + "&access_token=" + self.token
        r = requests.get(url, verify=self.cert_verify)
        if r.status_code != requests.codes.ok:
            logging.warning('get_records status code: %d', r.status_code)
        return r.json() if (r.status_code == requests.codes.ok) else None

    def get_record(self, record_id):
        url = self.url + "/api/records/" + record_id + "?access_token=" + self.token
        r = requests.get(url, verify=self.cert_verify)
        return r.json() if (r.status_code == requests.codes.ok) else None

    def create_draft(self, json_object):
        url = self.url + "/api/records/?access_token=" + self.token
        headers= { 'Content-Type' : 'application/json' }
        r = requests.post(url, data=json_object, headers=headers)
        if (r.status_code == requests.codes.created):
            return r.json()
        else:
            logging.warning('create_draft returned status code: %d', r.status_code)
            return None
        

    def put_draft_file(self, filebucket_url, file_list):
        
        headers= { 'Accept': 'application/json', 'Content-Type' : 'application/octet-stream' }
        out=[]
        for file_name in file_list:
            with open(file_name,'rb') as fid:
                url = filebucket_url + "/" + basename(file_name) + "?access_token=" + self.token
                r=requests.put(url, headers=headers, data=fid)
                if (r.status_code == requests.codes.ok):
                    out.append(r.json())
                else:
                    logging.warning('put_draft_file returned status code: %d', r.status_code)

        return out
            
    def get_drafts(self):
        url = self.url + "/api/records/?q=community:" + self.community_id + "&drafts=1&q=publication_state:draft&access_token=" + self.token
        r = requests.get(url, verify=self.cert_verify)
        if r.status_code != requests.codes.ok:
            logging.warning('get_drafts status code: %d', r.status_code)
        return r.json() if (r.status_code == requests.codes.ok) else None

    def get_draft(self, draft_id):
        url = self.url + "/api/records/" + draft_id + "/draft?access_token=" + self.token
        r = requests.get(url, verify=self.cert_verify)
        return r.json() if (r.status_code == requests.codes.ok) else None

    def mkdir_p(self, path):
        try:
            os.makedirs(path)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise

    def get_file(self, url_suffix):
        path = configuration.get('Main','tempDir') + url_suffix

        # a cached file, return the file path
        if os.path.isfile(path):
            return path

        url = self.url + url_suffix + "?access_token=" + self.token

        r = requests.get(url, verify=self.cert_verify)
        if r.status_code == requests.codes.ok:
            logging.debug('Receiving a file to %s', path)
            self.mkdir_p(os.path.dirname(path))
            chunk_size = 16 * 1024
            with open(path, 'wb') as fd:
                for chunk in r.iter_content(chunk_size):
                    fd.write(chunk)
                fd.close()
            return path

    def get_draft_file(self, draft):

        if draft is None:
            logging.warning('No draft')
            return None

        if 'files' in draft['links']:
            files_link = draft['links']['files'] + "?access_token=" + self.token
            logging.debug('draft: %s, files link: %s', draft['id'], files_link)
        else:
            logging.warning('draft: %s, no files, returning', draft['id'])
            return None

        r = requests.get(files_link, verify=self.cert_verify)
        if r.status_code == requests.codes.ok:
            files = r.json()
            logging.debug('draft %s, files: %s', draft['id'], files)
            if len(files['contents']) > 0:
                if len(files['contents']) > 1:
                    # TODO: filter by file type
                    logging.info('draft %s: more than one file, only using the first one', draft['id'])
                file_url = files['contents'][0]['links']['self']
                url_suffix = urlparse(file_url).path
                return self.get_file(url_suffix)
            else:
                logging.debug('draft %s: no files contents, returning', draft['id'])
                return None
        else:
            logging.warning('draft %s: get_draft_file, response code not ok: %d, %s', draft['id'], r.status_code, r.text)

        return None

    def update_draft(self, draft, json_patch):

        if not bool(json_patch):
            return None

        url = self.url + "/api/records/" + draft['id'] + "/draft?access_token=" + self.token
        headers = {'Content-Type': 'application/json-patch+json'}

        print("the patch is: ")
        print(json_patch)
        
        r = requests.patch(url, data=json_patch, headers=headers, verify=self.cert_verify)
        if r.status_code == requests.codes.ok:
            return_url = self.url + "/records/" + draft['id']
            logging.debug('draft %s: return url: %s', draft['id'], return_url)
            return return_url
        else:
            logging.warning('draft %s, update_draft: response code not ok: %d, url: %s, %s', draft['id'], r.status_code, url, r.text)

        return None

    def need_update(self, draft):

        # e.g. 2016-12-01T15:24:11.615881+00:00
        t1 = datetime.strptime(draft['created'].split("+")[0], "%Y-%m-%dT%H:%M:%S.%f")
        t2 = datetime.strptime(draft['updated'].split("+")[0], "%Y-%m-%dT%H:%M:%S.%f")
        difference = t2 - t1

        logging.debug('draft %s, updated: %s, created: %s, "diff (s): %s', draft['id'], draft['updated'].split("+")[0], draft['created'].split("+")[0], difference.seconds)

        if difference.seconds < configuration.getint('B2','update_time_criteria'):
            return True
        else:
            return False

    def generate_record_seq(self, input_queue):

        drafts = self.get_drafts()

        if drafts is not None:
            drafts_list = drafts['hits']['hits']
        else:
            return

        for draft in drafts_list:
            if self.need_update(draft):
                logging.debug('queueing draft %s', draft['id'])
                t = (1, draft['id'])
                # time.sleep(random.randint(1, 5))
                input_queue.put(t)

    def send_notification(self, url_list):

        url_text = "This is an automatically created message.\n"
        for url in url_list:
            url_text += str(url) + "/edit\n"

        logging.debug(url_text)

        msg = EmailMessage()
        msg.set_content(url_text)

        msg['Subject'] = configuration.get('B2','notification_subject')
        msg['From'] = configuration.get('B2','notification_from')

        for dest in configuration.get('B2','notification_to_list'):
            msg['To'] = dest
            s = smtplib.SMTP(configuration.get('B2','smtp_server_hostname'))
            s.set_debuglevel(1)
            s.sendmail(configuration.get('B2','notification_from'), dest, msg.as_string())
            s.quit()
