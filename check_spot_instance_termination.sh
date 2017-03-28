#!/usr/bin/env bash
if curl -s --max-time 5 http://169.254.169.254/latest/meta-data/spot/termination-time | grep -q .*T.*Z; then
  echo "spot instance termination imminent"
  # Create a file that Jenkins will archive so that the caller of this job can
  # detect this job needs to be re-kicked:
  touch spot_instance_termination_imminent.txt
  exit 1
else
  # Spot instance not yet marked for termination.
  echo "spot instance has not been marked for termination..."
  exit 0
fi
