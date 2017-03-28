import os
import sys
import argparse
from jenkinsapi.jenkins import Jenkins
try:
    btermcolor = True
    import termcolor
except:
    btermcolor = False

g_jenkins = None
g_jenkins_job = None

# Parse command line args:
def parseArgs():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--jenkins_username', help='Jenkins username.', default='alex.gray')
    parser.add_argument('--jenkins_password', help='Jenkins password.', default=os.environ['JENKINS_PASSWORD'])
    parser.add_argument('--jenkins_host', help='Jenkins host.', default=os.environ['JENKINS_URL'])
    parser.add_argument('--git_hash', help='Git Hash.', default=os.environ['ghprbActualCommit'])
    parser.add_argument('--worker_job', help='The job that does the work', default='unit-test-worker')
    parser.add_argument('--unit_test_file', help='File containing unit tests',
                        default=os.path.join(os.path.dirname(__file__), '..', 'my_app', 'unit_tests.txt'))
    args = parser.parse_args()
    return args


# We need to flush stdout for Jenkins:
def say(s, banner=None, color=None, use_termcolor=True):
    raw_s = s
    if banner is not None:
        s = '{}\n{}\n{}'.format(banner * 50, str(s), banner * 50)

    # If termcolor package is installed, use it:
    if btermcolor and use_termcolor is True:
        s = termcolor.colored(str(s), color=color, attrs=['bold', 'dark'])

    if file_name is not None:
        with open(file_name, 'a+') as fd:
            fd.write(str(raw_s) + '\n')
    sys.stdout.flush()


def build_job(host, build_name, params, username, password):
    print('Kicking off: {0}'.format(build_name))
    global g_jenkins
    global g_jenkins_job
    if g_jenkins is None:
        g_jenkins = Jenkins(host, username=username, password=password)
        g_jenkins_job = g_jenkins[build_name]
    # Invoke the job:
    q = g_jenkins_job.invoke(block=False, build_params=params)
    # Return immediately. Do not wait for job to finish:
    return q
