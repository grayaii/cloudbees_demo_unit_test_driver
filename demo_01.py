import os
import sys
import time
from jenkinsapi.custom_exceptions import NotBuiltYet
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from common import parseArgs, say, build_job


def kick_off_jobs(test_file):
    say('Kicking off all the workers...', banner='*')
    ret_jenkins_queue_jobs = []
    # Get all the tests from the tests.txt:
    all_tests = []
    with open(test_file, 'r') as fd:
        for test in fd.readlines():
            if test.strip() != '':
                all_tests.append(test.strip())
    say('num of tests  : {}'.format(len(all_tests)))
    say('These are the tests that set to be executed on this run:')
    for test in all_tests:
        say('test: {0}'.format(test))

    for test in all_tests:
        # For each test group, call a jenkins job to run them sequencially:
        params = {
            'GIT_HASH': args.git_hash,
            'UPSTREAM_BUILD_NUMBER': os.environ.get('BUILD_NUMBER', 'manual'),
            'TEST': test
        }
        # Put these jobs on the queue:
        r = build_job(host=args.jenkins_host,
                      build_name=args.worker_job,
                      params=params,
                      username=args.jenkins_username,
                      password=args.jenkins_password)
        ret_jenkins_queue_jobs.append(r)
    return ret_jenkins_queue_jobs

def driver(test_file):
    # Kick off all jenkins jobs:
    jenkins_queue_jobs = kick_off_jobs(test_file)
    say('Waiting for all worker jobs to get off the jenkins queue...', banner='*')
    builds = []
    for q in jenkins_queue_jobs:
        while True:
            try:
                q.poll()
                builds.append(q.get_build())
                break
            except NotBuiltYet:
                say('still on the queue: {0}'.format(q))
                time.sleep(10)
                continue
            except requests.exceptions.HTTPError as ex:
                # Edge case where queue item is off the queue
                # and has been deleted by Jenkins
                if ex.response.status_code == 404:
                    say('breaking out of loop for this item on the queue...')
                    break

    say('All jobs off the queue! Waiting for all jobs to finish...', banner='*')
    ret_code = 0
    master_results = []
    while len(builds) > 0:
        say('*' * 75)
        for r in builds:
            b.poll()
            if b.is_running() is True:
                say('Still building: {0} url: {1}'.format(b.name, b.baseurl))
                isBuilding = True
                time.sleep(15)
            else:
                # It takes one more poll to get the results:
                b.poll()
                say('Build Done: {0} status: {1}'.format(b.baseurl, b.get_status()))
                # Regardless of what happened, the worker is done, so
                # take it off the list
                if b.get_status() != 'SUCCESS':
                    ret_code += 1
                master_results.append(r)
                builds.remove(r)

    say('Results', banner='*')
    for build in master_results:
        say('Status: {0}, URL: {1}'.format(build.get_status(), build.baseurl))
    say('All done!')
    return ret_code


if __name__ == '__main__':
    args = parseArgs()
    driver(test_file=args.unit_test_file)
