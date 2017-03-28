import os
import sys
import time
import requests
from jenkinsapi.custom_exceptions import NotBuiltYet
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from common import parseArgs, say, build_job


def update_in_progress_file(aStr=None, q=None):
    # This file is used if the driver job gets cancelled.
    # The cleanup post build script uses this file to abort the running worker jobs.
    if aStr is not None:
        with open(os.path.join('unit_test_workers_file.txt'), 'a') as fd:
            fd.write(aStr)
    else:
        # We need to remove the queue item and add the build number:
        new_contents = []
        with open(os.path.join('unit_test_workers_file.txt'), 'r') as fd:
            for line in fd:
                if line.split(',')[1].strip() != q.baseurl:
                    new_contents.append(line)
        with open(os.path.join('unit_test_workers_file.txt'), 'w') as fd:
            for line in new_contents:
                fd.write(line)
        # Add the build number:
        update_in_progress_file(aStr='{0},{1}\n'.format(args.unit_test_driver, q=q.get_build().get_number()))

def kick_off_jobs(test_file):
    say('Kicking off all the workers...', banner='*', color='green')
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
        update_in_progress_file(aStr='{0},{1}\n'.format(args.worker_job, r.baseurl))
    return ret_jenkins_queue_jobs

def driver(test_file):
    # Kick off all jenkins jobs:
    jenkins_queue_jobs = kick_off_jobs(test_file)
    say('Waiting for all worker jobs to get off the jenkins queue...', banner='*', color='green')
    builds = []
    for q in jenkins_queue_jobs:
        while True:
            try:
                q.poll()
                builds.append(q.get_build())
                update_in_progress_file(aStr=None, q=q)
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

    say('All jobs off the queue! Waiting for all jobs to finish...', banner='*', color='green')
    ret_code = 0
    master_results = []
    while len(builds) > 0:
        say('*' * 75)
        for b in builds:
            b.poll()
            if b.is_running() is True:
                say('Still building: {0} url: {1}'.format(b.name, b.baseurl))
                isBuilding = True
                time.sleep(15)
            else:
                # It takes one more poll to get the results:
                b.poll()
                say('Build Done: {0} status: {1}'.format(b.baseurl, b.get_status()))
                say('Downloading artifacts...')
                artifact_dict = b.get_artifact_dict()
                if 'spot_instance_termination_imminent.txt' in artifact_dict:
                    say('spot_instance_termination_imminent.txt in artifact. We must kick off new worker...')
                    # Uh-oh. Worker died due to spot instance dying.
                    # re-kick this job and wait till it's off the queue and building:
                    actions = b.get_data(b.baseurl + '/api/python')['actions']
                    params = {}
                    for action in actions:
                        if 'parameters' in action:
                            for param in action['parameters']:
                                params[param['name']] = param['value']
                        break
                    # Put this jobs on the queue:
                    q = build_job(host=args.jenkins_host,
                                  build_name=args.unit_test_driver,
                                  params=params,
                                  username=args.jenkins_username,
                                  password=args.jenkins_password)
                    # and wait for it to get off the queue:
                    while True:
                        try:
                            q.poll()
                            builds.append(q.get_build())
                            update_in_progress_file(aStr=None, q=q)
                            break
                        except NotBuiltYet:
                            say('still on the queue: {0}'.format(q))
                            time.sleep(15)
                            continue
                        except requests.exceptions.HTTPError as ex:
                            # Edge case where queue item is off the queue
                            # and has been deleted by Jenkins
                            if ex.response.status_code == 404:
                                say('breaking out of loop for this item on the queue...')
                                break
                else:
                    # The worker is done:
                    for artifact_name, v in artifact_dict.items():
                        say('Saving artifact to: {0}'.format(os.path.join(args.artifact_dir, artifact_name)))
                        for i in range(5):
                            try:
                                v.save(os.path.join(args.artifact_dir, artifact_name), strict_validation=False)
                                break
                            except Exception as ex:
                                say(ex)
                                say('Carry on despite this exception...')
                                time.sleep(3)
                # Regardless of what happened, the worker is done, so
                # take it off the list
                if b.get_status() != 'SUCCESS':
                    ret_code += 1
                master_results.append(b)
                builds.remove(b)

    say('Results', banner='*', color='green')
    for build in master_results:
        say('Status: {0}, URL: {1}'.format(build.get_status(), build.baseurl))
    say('All done!')
    return ret_code


if __name__ == '__main__':
    args = parseArgs()
    driver(test_file=args.unit_test_file)
