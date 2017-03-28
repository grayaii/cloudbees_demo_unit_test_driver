import os
import sys
import time
import json
import argparse
import threading
import traceback
import subprocess
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from common import say


# Parse command line args:
def parseArgs():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--build_number', help='Build number. Only used to generate unique results file.', default='0')
    args = parser.parse_args()
    return args


def run(cmd):
        output = None
        returncode = None
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, shell=True)
            output = p.communicate()[0]
            returncode = p.returncode
        except Exception:
            say('***Error in command: {0}'.format(cmd))
            say('Exception:----------------')
            say(traceback.format_exc())
            say('--------------------------')

        return output, returncode


def check_spot_instance_termination():
    while True:
        script_to_run = os.path.abspath(os.path.join(os.path.dirname(__file__), 'check_spot_instance_termination.sh'))
        output, returncode = run(script_to_run)
        if returncode == 1:
            say('The instance is about to be terminated! Exiting script now!')
            os._exit(1)
        say(output)
        time.sleep(5)


if __name__ == '__main__':
    args = parseArgs()

    # Run thread that checks if spot instance is about to be destroyed:
    thread = threading.Thread(target=check_spot_instance_termination)
    thread.daemon = True
    thread.start()

    # Run all the tests:
    output, returncode = run(os.environ.get('TEST', 'echo "no tests!"'))
    say('OUTPUT: \n{}'.format(output))
    sys.exit(returncode)
