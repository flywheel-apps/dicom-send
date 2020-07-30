#!/usr/bin/env python3
"""Main script for dicom-send gear."""

import os

import flywheel_gear_toolkit

from utils import parse_config
from utils import dicom_send


def main(gear_context):
    """Orchestrate dicom-send gear."""
    log.info("Starting dicom-send gear.")

    # Prepare gear arguments by parsing the gear configuration
    gear_args, download = parse_config.generate_gear_args(gear_context)

    # Run dicom-send
    if download is True:

        DICOMS_SENT = dicom_send.download_and_send(**gear_args)

    elif download is False:

        DICOMS_SENT = dicom_send.run(**gear_args)

    # Log number of DICOM files transmitted and exit accordingly
    if DICOMS_SENT == 0:
        log.error("No DICOM files were transmitted. Exiting.")
        os.sys.exit(1)
    else:
        log.info(f"!!! TOTAL -- There were {DICOMS_SENT} DICOM files transmitted.")
        exit_status = 0
        return exit_status


if __name__ == "__main__":

    with flywheel_gear_toolkit.GearToolkitContext() as gear_context:

        log = gear_context.log
        exit_status = main(gear_context)

    log.info(f"Successful dicom-send gear execution with exit status {exit_status}.")
