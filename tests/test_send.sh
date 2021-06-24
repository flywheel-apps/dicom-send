#!/bin/bash

storescu -v --scan-directories -aet AE_send -aec AE_rec \
    -xf /tmp/storescu.cfg Default \
    192.168.11.23 4242 /flywheel/v0/test_data/image1.dcm

storescu -v --scan-directories -aet AE_send -aec AE_rec \
    -xf /tmp/storescu.cfg Default \
    192.168.11.23 4242 /flywheel/v0/test_data/TRACKFA_QA_LW_MRS.dcm
