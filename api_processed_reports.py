# !/usr/bin/env python
#  -*- coding: utf-8 -*-
# title             :api_processed_reports.py
# description       :This script will grab processed report from Triage and push it to Splunk using the HTTP Event
#                    Controller input.
# author            :Micheal L Palmer Jr
# date              :7 June 2019
# version           :0.0.1
# usage             :External script
# python_version    :3.7

# INFO INFO INFO
#
# Please be advised that a default Splunk install will truncate events to the first 10,000 bytes. This can be configured
# via the TRUNCATE variable in the /local props.conf file to allow the full event to appear in Splunk. Set this value
# to 0 or value deemed appropriate by your Splunk administration. If this is not changed, you will have missing data
# that either makes the Splunk parsing of the JSON fail due to missing pieces, inaccurate metrics reporting, or other
# unknown experiences. Splunk does not recommend changing the props.conf file in the /default directory.  Please refer
# to this page for more information:
#
# https://docs.splunk.com/Documentation/Splunk/6.0.3/Admin/Propsconf#
#
# Sample props.conf file in local:
# [default]
# CHARSET=AUTO
# TRUNCATE = 0
# MAX_EVENTS = 1024#
#
# Additionally, this script will need to be adjusted to accommodate your network and policy requirements.
#
# INFO INFO INFO

# Requests is a native module to Python3 after a pip install of that module has occurred. To install Requests using pip
# please follow this reference:
# http://docs.python-requests.org/en/master/user/install/

# Native Python Imports
# import logging.handlers
import json
import requests
import datetime

# Disable InsecureRequestWarning (Securing request would require substantial amount more work on the script. Please
# contact your Client Success representative if you wish to pursue this route.)

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Generic Variables

# Setup Logging.
# Logging is handled via syslog.
# logger_port = 514
# logger_address = ('localhost', logger_port)
# logger_handler = logging.handlers.SysLogHandler(logger_address)
# logger_handler.setLevel(logging.INFO)
# logger_format = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(message)s')
# logger_handler.setFormatter(logger_format)
# logger = logging.getLogger('api_processed_reports')
# logger.addHandler(logger_handler)

# Triage Variables

# The Triage domain is the URL that you use to access the Triage UI. This must be in the format of
# https://subdomain.domain.com or https://192.168.0.1. There should be no ending forward slash (/). This is accounted
# for in the path variable.
triage_domain = '<USE DOMAIN>
# The Triage account and token need to be setup in the Triage API. The account must be a superuser account before an
# API token can be generated.
triage_api_account = 'sample_user@example.com'
triage_api_token = 'abcdefghijklmnopqrstuvwxyz012345'
triage_headers = {'Authorization': 'Token token=' + triage_api_account + ':' + triage_api_token}

# The default pull time for APIs is set to 6 days. This is longer than necessary. by setting the datetime.timedelta
# value to (hours=2) we are pulling just for the last 2 hours. You can adjust this to any value for days=, hours=, or
# minutes=)
date_today = datetime.date.today()
api_pull_earliest_date = datetime.datetime.now() - datetime.timedelta(hours=2)
api_pull_date = api_pull_earliest_date.strftime('%Y-%m-%dT%H:%M')


# Splunk Variables

# The HTTP Event Collector headers and URL are generated in the Splunk device. The default setting for the HEC collector
# is on port 8088 of the Splunk device. Please follow this reference for information on how to generate an HEC token and
# setup the collector:
# https://docs.splunk.com/Documentation/Splunk/latest/Data/UsetheHTTPEventCollector
splunk_hec_headers = {'Authorization': 'Splunk splunk-0123-token-4567-generated'}
splunk_hec_url = 'https://splunkdomain.example.com:8088/services/collector'


def main(domain, api_headers, pull_start_date, hec_headers, hec_url):
    try:
        triage_api_call_path = '/api/public/v1/processed_reports'
        # This will pull the page count for the last 2 hours as defined by the api_pull_earliest_date variable in the
        # Generic variables. If you wish to pull for more you will need to adjust the datetime.timedelta argument from
        # hours=2 to days=XX (i.e. datetime.timedelta(days=365)). This argument can include both hours and days if you
        # need to be specific (i.e. datetime.timedelta(days=1, hours=5)).
        page_count_request_url = f'{domain}{triage_api_call_path}?per_page=50&start_date={pull_start_date}'
        page_count_request = requests.get(page_count_request_url, verify=False, headers=api_headers)
        page_count = (int(page_count_request.headers['Total']) // 50) + 1

        # This will take any page count of 0 returned due to math above and set it to one(1). Triage can pull for
        # '?page=0', but it's better to remain consistent with a start of '&page=1'. The variable should technically
        # never have a 0 due to the '+1' in the equation, but stranger things have happened.
        if page_count == 0:
            page_count = 1

        # This will run a loop through each page from one(1) to the total in page_count. The resulting page is a JSON
        # array.
        for each_page in range(1, page_count + 1):
            processed_data_url = f'{domain}{triage_api_call_path}' \
                f'?page={str(each_page)}' \
                f'&per_page=50' \
                f'&start_date={pull_start_date}'
            processed_data_request = requests.get(processed_data_url, verify=False, headers=api_headers)
            processed_data = json.loads(processed_data_request.content)

            # This will loop through each JSON object in the JSON array. It will take the 'updated_at' field, the
            # timestamp of when it was processed, and use that as the Splunk event timestamp. It converts it to the
            # epoch format that Splunk expects. You can adjust updated_at_time if you wish to use a different JSON
            # field for the Splunk event timestamp (such as 'created_at').
            for each_json in processed_data:
                updated_at_time = each_json['updated_at']
                updated_at_epoch = datetime.datetime.strptime(updated_at_time, '%Y-%m-%dT%H:%M:%S.%fZ')

                # The HTTP Event Collector payload can be configured using the following reference guide:
                # http://dev.splunk.com/view/event-collector/SP-CAAAE6P#data
                hec_payload = {'sourcetype': '_json',  # This is the sourcetype of the event.
                               'source': 'api:processed_reports',
                               'time': updated_at_epoch.timestamp(),
                               'host': domain,  # This is the value that will populate Splunk's 'host' field.
                               'index': 'triage',  # This is the index to which the event is pushed. You can remove this
                                             # field if you wish to use the default index configured in the Splunk HEC
                                             # configuration page.
                               'event': json.dumps(each_json)}

                # Once the HEC payload has been generated for the JSON object, it will be pushed to Splunk.
                splunk_post = requests.post(hec_url, data=json.dumps(hec_payload).encode('utf8'),
                                            headers=hec_headers, verify=False)
                if str(splunk_post.status_code) == '200':
                    pass
    except json.decoder.JSONDecodeError:
        pass
    except Exception as error:
        # logging.critical(error)
        print(error)


if __name__ == '__main__':
    main(triage_domain,
         triage_headers,
         api_pull_date,
         splunk_hec_headers,
         splunk_hec_url)
