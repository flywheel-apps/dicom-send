"""Function to parse gear config into gear args."""

import logging
import pprint
from pathlib import Path

import flywheel

log = logging.getLogger(__name__)


def generate_gear_args(gear_context):
    """Generate gear arguments."""
    log.info("Preparing arguments for dicom-send gear.")
    gear_kwargs = {
        "work_dir": gear_context.work_dir,
        "destination": gear_context.config["destination"],
        "called_ae": gear_context.config["called_ae"],
        "port": gear_context.config["port"],
        "calling_ae": gear_context.config["calling_ae"],
        "group": "0x0021",
        "identifier": "Flywheel",
        "tag_value": "DICOM Send",
        'api_key': gear_context.get_input("api_key")["key"]
    }
    
    fw = flywheel.Client(gear_kwargs['api_key'])
    
    
    # Input is a tgz or zip DICOM archive, or a single DICOM file
    try:
        infile = Path(gear_context.get_input_path("file"))
        download = not infile.is_file()
    except TypeError:
        download = True
        log.info("No input provided. Will use files of type DICOM from session.")

    if download is False:
        gear_kwargs["infile"] = infile
        gear_kwargs["parent_acq"] = gear_context.get_input("file")["hierarchy"].get("id")
        gear_kwargs['session_id'] = fw.get_acquisition(gear_kwargs["parent_acq"]).parents.session

    else:
        # Alternatively, if no input is provided, all DICOM files in the session are
        # downloaded and used as input
        gear_kwargs['session_id'] = gear_context.destination["id"]
        gear_kwargs['input_dir'] = "/flywheel/v0/input"
    
    
    gear_args_formatted = pprint.pformat(gear_kwargs)
    log.info(f"Prepared gear stage arguments: \n\n{gear_args_formatted}\n")

    return gear_kwargs, download
