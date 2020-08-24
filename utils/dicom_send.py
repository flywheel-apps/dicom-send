"""Functions to run dicom-send."""

import logging
import os
import shutil
import tarfile
import zipfile
from pathlib import Path

import pydicom
import flywheel

from utils import tag_and_transmit
from utils import report_generator


log = logging.getLogger(__name__)


def prepare_work_dir_contents(infile, work_dir):
    """Prepare dicom-send input directory.

        The input can be a zip archive (.zip), a compressed tar archive (.tgz), or a
        single DICOM file. Input contents are placed into the working directory.

    Args:
        infile (pathlib.PosixPath): The absolute path to the input file.
        work_dir (pathlib.PosixPath): The absolute path to the working directory where
            the DICOM files are placed.

    Returns:
        None.

    """
    log.info("Arrange dicom-send input.")

    if zipfile.is_zipfile(infile):

        try:

            with zipfile.ZipFile(infile, "r") as zip_obj:
                log.info(f"Establishing input as zip file: {infile}")
                exit_if_archive_empty(zip_obj)
                zip_obj.extractall(work_dir)

        except zipfile.BadZipFile:
            log.exception(
                (
                    "Incorrect gear input. "
                    "File is not a zip archive file (.zip). Exiting."
                )
            )
            os.sys.exit(1)

    elif tarfile.is_tarfile(infile):

        try:
            with tarfile.open(infile, "r") as tar_obj:
                log.info(f"Establishing input as tar file: {infile}")
                exit_if_archive_empty(tar_obj)
                tar_obj.extractall(work_dir)

        except tarfile.ReadError:
            log.exception(
                (
                    "Incorrect gear input. "
                    "File is not a compressed tar archive file (.tgz). Exiting."
                )
            )
            os.sys.exit(1)

    else:
        log.info(f"Establishing input as single DICOM file: {infile}")
        try:
            # If valid DICOM file, move to working directory; otherwise, exit
            pydicom.filereader.dcmread(infile, force=True)
            shutil.copy2(infile, work_dir)
        except pydicom.errors.InvalidDicomError:
            log.info("Input file is not a valid DICOM file. Exiting.")
            os.sys.exit(1)

    log.info("Input for dicom-send prepared successfully.")


def exit_if_archive_empty(archive_obj):
    """If the archive contents are empty, log an error and exit."""
    if type(archive_obj) == zipfile.ZipFile:
        size_contents = sum([zipinfo.file_size for zipinfo in archive_obj.filelist])

    elif type(archive_obj) == tarfile.TarFile:
        size_contents = sum([tarinfo.size for tarinfo in archive_obj.getmembers()])

    else:
        log.info(
            "Unsupported archive format. Unable to establish size of input archive. "
            "Exiting."
        )
        os.sys.exit(1)

    if size_contents == 0:
        log.error("Incorrect gear input. Input archive is empty. Exiting.")
        os.sys.exit(1)


def download_and_send(
    api_key,
    session_id,
    input_dir,
    work_dir,
    destination,
    called_ae,
    port=104,
    calling_ae="flywheel",
    group="0x0021",
    identifier="Flywheel",
    tag_value="DICOM Send",
):
    """Download files in the session where the file type is DICOM.

    Args:
        api_key (str): The API key required to access the session in a Flywheel
            instance.
        session_id (str): The session ID from a Flywheel instance from which to
            download files from.
        input_dir (pathlib.PosixPath): The absolute path to the input directory where
            the DICOM files are downloaded to.
        work_dir (pathlib.PosixPath): The absolute path to the working directory where
            the DICOM files are placed.
        destination (str):The IP address or hostname of the destination DICOM server.
        called_ae (str):The Called AE title of the receiving DICOM server.
        port (int) = Port number of the listening DICOM service.
        calling_ae (str): The Calling AE title.
        group (str): The DICOM tag group to use when applying tag to DICOM file.
        identifier (str): The private tag creator name to use as identification.
        tag_value (str): The value to associate the private tag with.

    Returns:
        DICOMS_SENT (int): The number of DICOM files transmitted.

    """
    log.info("Downloading DICOM files.")
    DATA_FLAG = False
    DICOMS_SENT = 0

    # Create input directory if it doesn't exist
    if not Path(input_dir).is_dir():
        os.mkdir(input_dir)
    
    # Instantiate instance connection and load acquisitions in session
    fw = flywheel.Client(api_key)
    acquisitions = fw.get_session_acquisitions(session_id)

    # In a session, the possible downloads include any combination of:
    # zip archive, tgz archive, a single DICOM file, multiple DICOM files, or empty.
    # All cases are handled by parsing the downloaded files in the input directory
    # and calling downstream functions accordingly.
    for acq in acquisitions:
        for file in acq.get("files"):
            if file.type == "dicom":

                file_path = Path(f"{input_dir}/{file.name}")
                fw.download_file_from_acquisition(acq.id, file.name, file_path)
    
                if file_path.is_file():
                    # A file with file.type = dicom has been downloaded
                    DATA_FLAG = True

                    dicoms_sent = run(
                        fw,
                        acq.id,
                        file_path,
                        work_dir,
                        destination,
                        called_ae,
                        port,
                        calling_ae,
                        group,
                        identifier,
                        tag_value,
                    )
                    DICOMS_SENT += dicoms_sent

                    # Remove contents of working directory because we assume multiple
                    # downloaded files and need a clean workspace for each run.
                    shutil.rmtree(work_dir)
                    os.mkdir(work_dir)

    if DATA_FLAG is False:
        log.error(
            "No DICOM files were available for download for session with ID: "
            f"{session_id}. The file.type must be set to dicom for download "
            "to occur. Exiting."
        )
        os.sys.exit(1)

    return DICOMS_SENT


def run(
    fw,
    parent_acq,
    infile,
    work_dir,
    destination,
    called_ae,
    port=104,
    calling_ae="flywheel",
    group="0x0021",
    identifier="Flywheel",
    tag_value="DICOM Send",
):
    """Run dicom-send, including tagging each DICOM file and transmitting.

    Args:
        infile (pathlib.PosixPath): The absolute path to the input file.
        work_dir (pathlib.PosixPath): The absolute path to the working directory where
            the DICOM files are placed.
        destination (str):The IP address or hostname of the destination DICOM server.
        called_ae (str):The Called AE title of the receiving DICOM server.
        port (int) = Port number of the listening DICOM service.
        calling_ae (str): The Calling AE title.
        group (str): The DICOM tag group to use when applying tag to DICOM file.
        identifier (str): The private tag creator name to use as identification.
        tag_value (str): The value to associate the private tag with.

    Returns:
        DICOMS_SENT (int): The number of DICOM files transmitted.

    """
    prepare_work_dir_contents(infile, work_dir)

    DICOMS_PRESENT, DICOMS_SENT = tag_and_transmit.run(
        work_dir, destination, called_ae, port, calling_ae, group, identifier, tag_value
    )

    report_generator.generate_report(fw, parent_acq, infile.name, DICOMS_PRESENT, DICOMS_SENT)
    
    
    
    return DICOMS_SENT
