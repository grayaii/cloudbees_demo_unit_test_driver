import argparse
import os
import sys
import requests
from jenkinsapi.jenkins import Jenkins
import jenkinsapi
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from common import parseArgs, say, build_job


# Parse command line args:
def parseArgs():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--unit_test_workers_file', help='File containing list of queue items to stop.',
                        default='unit_test_workers_file.txt')
    parser.add_argument('--jenkins_username', help='Jenkins username.',
                        default='alex.gray')
    parser.add_argument('--jenkins_password', help='Jenkins password.',
                        default=os.environ.get('JENKINS_PASSWORD', 'Unknown password'))
    parser.add_argument('--jenkins_host', help='Jenkins host.',
                        default=os.environ.get('JENKINS_URL', 'Unknown user'))
    args = parser.parse_args()
    return args


def stop_all_workers(unit_test_workers_file, jenkins_host, jenkins_username, jenkins_password):
    if not os.path.exists(unit_test_workers_file):
        say('File does not exist: {0}'.format(unit_test_workers_file))
        say('Not doing anything. Exiting with success')
        sys.exit(0)
    with open(unit_test_workers_file, 'r') as fd:
        unit_test_workers = [line.strip().split(',') for line in fd.readlines() if line != '']

    J = Jenkins(jenkins_host, username=jenkins_username, password=jenkins_password)

    for unit_test_worker in unit_test_workers:
        queue_url = unit_test_worker[1].strip()
        build_name = unit_test_worker[0].strip()
        # Lets create a queue item from the job that is on the queue:
        if jenkins_host in queue_url:
            q = None
            try:
                say('Getting queue item: {0}'.format(queue_url))
                q = jenkinsapi.queue.QueueItem(queue_url, J)
            except jenkinsapi.custom_exceptions.JenkinsAPIException as ex:
                if 'Powered by Jetty' in ex.message:
                    say('Ignorning Jenkins benign exception...')
                else:
                    raise
            except requests.exceptions.HTTPError as ex:
                # Who cares if it's off the queue (This is an edge case):
                say('Ignorning error...')
            try:
                if q is not None:
                    q.get_job().delete_from_queue()
                    say('Job deleted from queue: {0}'.format(q))
            except (jenkinsapi.custom_exceptions.NotInQueue, jenkinsapi.custom_exceptions.JenkinsAPIException) as ex:
                # Job not on queue, so try to get the build:
                if q is not None:
                    say('Job not in queue. stopping build...')
                    b = q.get_build()
                    b.poll()
                    b.stop()
                    say('Job stopped: {0}'.format(b))
        else:
            # Item is off the queue, so simply stop the build:
            job = J[build_name]
            job.get_build(int(queue_url)).stop()


if __name__ == '__main__':
    args = parseArgs()
    stop_all_workers(unit_test_workers_file=args.unit_test_workers_file,
                     jenkins_host=args.jenkins_host,
                     jenkins_username=args.jenkins_username,
                     jenkins_password=args.jenkins_password)
