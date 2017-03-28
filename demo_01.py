import os
import sys
from jenkinsapi.custom_exceptions import NotBuiltYet
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from common import parseArgs


def driver(test_file, num_of_workers):
    # Kick off all jenkins jobs:
    jenkins_queue_jobs = kick_off_jobs(test_file, num_of_workers)
    say('Waiting for all worker jobs to get off the jenkins queue...', banner='*')
    results = []
    for q in jenkins_queue_jobs:
        while True:
            try:
                q.poll()
                results.append(q.get_build())
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

    say('All jobs off the queue! Waiting for all jobs to finish...', banner='*')
    ret_code = 0
    master_results = []
    while len(results) > 0:
        say('*' * 75)
        for r in results:
            r.poll()
            if r.is_running() is True:
                say('Still building: {0} url: {1}'.format(r.name, r.baseurl))
                isBuilding = True
            else:
                # It takes one more poll to get the results:
                r.poll()
                say('Build Done: {0} status: {1}'.format(r.baseurl, r.get_status()))
                say('Downloading artifacts...')
                artifact_dict = r.get_artifact_dict()
                if 'spot_instance_termination_imminent.txt' in artifact_dict:
                    say('spot_instance_termination_imminent.txt in artifact. We must kick off new worker...')
                    # Uh-oh. Worker died due to spot instance dying.
                    # re-kick this job and wait till it's off the queue and building:
                    actions = r.get_data(r.baseurl + '/api/python')['actions']
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
                            results.append(q.get_build())
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
                if r.get_status() != 'SUCCESS':
                    ret_code += 1

                master_results.append(r)
                results.remove(r)
        time.sleep(30)
    say('Results', banner='*')
    for build in master_results:
        say('Status: {0}, URL: {1}'.format(build.get_status(), build.baseurl))
    say('All done!')
    return ret_code


if __name__ == '__main__':
    args = parseArgs()
