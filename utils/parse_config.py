"""Function to parse gear config into gear args."""

import logging
import pprint
from pathlib import Path

log = logging.getLogger(__name__)


def generate_gear_args(gear_context):
    """Generate gear arguments."""
    log.info("Preparing arguments for dicom-send gear.")

    gear_args = {
                "destination": gear_context.config["destination"],
                "port": gear_context.config["port"],
                "called_ae": gear_context.config["called_ae"],
                "calling_ae": gear_context.config["calling_ae"],
                "group": "0x0021",
                "identifier": "Flywheel",
                "tag_value": "DICOM Send",
                "work_dir": gear_context.work_dir
                }

    # Input is a tgz or zip DICOM archive, or a single DICOM file
    infile = Path(gear_context.get_input_path("file"))

    if infile.is_file():

        gear_args['infile'] = infile
        download = False

    else:

        # Alternatively, if no input is provided, all DICOM files in the session are
        # downloaded and used as input
        gear_args['session_id'] = gear_context.destination["id"]
        gear_args["api_key"] = gear_context.get_input("api_key")['key']
        gear_args["input_dir"] = "/flywheel/v0/input"
        download = True

    gear_args_formatted = pprint.pformat(gear_args)
    log.info(f"Prepared gear stage arguments: \n\n{gear_args_formatted}\n")

    return gear_args, download
