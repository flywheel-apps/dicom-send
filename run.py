#!/usr/bin/env python3
"""Main script for dicom-send gear."""

import logging
import sys

import flywheel_gear_toolkit

from fw_gear_dicom_send import parser
from fw_gear_dicom_send import dicom_send
from fw_gear_dicom_send import report_generator

log = logging.getLogger(__name__)


def main(gear_context):
    """Orchestrate dicom-send gear."""
    log.info("Starting dicom-send gear.")

    # Prepare gear arguments by parsing the gear configuration
    gear_args, download, tls = parser.generate_gear_args(gear_context)
    dcms_present, dcms_sent = 0, 0

    gear_args['tls'] = tls
    # Run dicom-send
    session_id = None
    if download is True:
        dcms_present, dcms_sent = dicom_send.download_and_send(**gear_args)
        session_id = gear_args['session_id']

    elif download is False:
        session_id = gear_args.pop('session_id')
        dcms_present, dcms_sent = dicom_send.run(**gear_args)

    report_generator.upload_report(gear_args['api_key'], session_id, gear_args.get('parent_acq'))

    # Log number of DICOM files transmitted and exit accordingly
    if dcms_sent == 0:
        log.error("No DICOM files were transmitted. Exiting.")
        sys.exit(1)
    elif dcms_sent < dcms_present:
        log.error(
            "Not all DICOMS were successfully transmitted "
            f"({dcms_sent}/{dcms_present}). Please check report."
        )
        sys.exit(1)
    else:
        log.info(f"!!! TOTAL -- There were {dcms_sent} DICOM files transmitted.")
        exit_status = 0
        return exit_status


if __name__ == "__main__":

    with flywheel_gear_toolkit.GearToolkitContext() as gear_context:
        gear_context.init_logging()
        exit_status = main(gear_context)

    log.info(f"Dicom-send gear execution with exit status {exit_status}.")
