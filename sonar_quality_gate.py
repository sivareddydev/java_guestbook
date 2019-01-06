
import os
import subprocess
import requests
import json
import time

time.sleep(10)

work_space = os.environ['WORKSPACE']
sonar_auth_token = os.environ['sonarAuthToken']

if not os.path.isdir(work_space + '/target/sonar'):
    os.makedirs(work_space + '/target/sonar')

if not os.path.isdir(work_space + '/.sonar'):
    os.makedirs(work_space + '/.sonar')

if not os.path.isfile(work_space + '/target/sonar/report-task.txt'):
    subprocess.call(['ln', '-s', work_space+'/.sonar/report-task.txt', work_space+'/target/sonar/report-task.txt'])


with open(work_space+'/target/sonar/report-task.txt') as f:
    report_file = f.readlines()

for r in report_file:
    if 'ceTaskUrl' in r:
        url = r[10::]
print "URL from reports:", url

# Fetching Task attributes from Sonar Server
urlreq = requests.get(url, auth=(sonar_auth_token, ''))
print json.dumps(urlreq.json(), indent=2)

# Setting up task status to check if sonar scan is completed successfully.
data = urlreq.json()
passed = True
