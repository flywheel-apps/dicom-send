"""Functions to run dicom-send."""

import logging
import os
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path

import backoff
from fw_file.dicom import DICOMCollection
from fw_core_client import CoreClient, ClientError, ServerError

from . import tag_and_transmit
from . import report_generator
from .parser import get_client, TLSOpt

log = logging.getLogger(__name__)


def prepare_work_dir_contents(infile, work_dir):
    """Prepare dicom-send input directory.

        The input can be a zip archive (.zip), a compressed tar archive (.tgz), or a
        single DICOM file. Input contents are placed into the working directory.

    Args:
        infile (pathlib.PosixPath): The absolute path to the input file.
        work_dir (pathlib.PosixPath): The absolute path to the working directory where
            the DICOM files are placed.
    """
    log.info("Arrange dicom-send input.")

    if zipfile.is_zipfile(infile):
        log.info("Found input zipfile {infile}, unzipping")
        try:
            with zipfile.ZipFile(infile, "r") as zip_obj:
                exit_if_archive_empty(zip_obj)
                zip_obj.extractall(work_dir)
        except zipfile.BadZipFile:
            log.exception("Input looks like a zip but is not valid")
            sys.exit(1)

    elif tarfile.is_tarfile(infile):
        log.info("Found input tarfile {infile}, untarring")
        try:
            with tarfile.open(infile, "r") as tar_obj:
                exit_if_archive_empty(tar_obj)
                tar_obj.extractall(work_dir)
        except tarfile.ReadError:
            log.exception("Input looks like a tar but is not valid")
            sys.exit(1)

    else:
        log.info(f"Establishing input as single DICOM file: {infile}")

    log.info("Input for dicom-send prepared successfully.")


def exit_if_archive_empty(archive_obj):
    """If the archive contents are empty, log an error and exit."""
    size = 0
    if isinstance(archive_obj, zipfile.ZipFile):
        size = sum([zipinfo.file_size for zipinfo in archive_obj.filelist])
    elif isinstance(archive_obj, tarfile.TarFile):
        size = sum([tarinfo.size for tarinfo in archive_obj.getmembers()])
    else:
        log.info(
            "Unsupported archive format. Unable to establish size of input archive. "
            "Exiting."
        )
        sys.exit(1)

    if size == 0:
        log.error("Incorrect gear input. Input archive is empty. Exiting.")
        sys.exit(1)

def get_retry_time() -> int:
    """Helper function to return retry time from env."""
    return int(os.getenv("FLYWHEEL_DOWNLOAD_RETRY_TIME", "10"))


@backoff.on_exception(backoff.expo, ServerError, max_time=get_retry_time)
def download_file(fw: CoreClient, acq_id: str, file_name: str, dest: Path):
    """Download file from acquisition with retry."""
    resp = fw.get(f"/acquisitions/{acq_id}/files/{file_name}", stream=True)
    with open(dest, 'wb') as fp:
        fp.write(resp.content)


def download_and_send(
    api_key,
    session_id,
    input_dir,
    work_dir,
    destination,
    called_ae,
    tls: TLSOpt,
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
        tls (TLSOpt): TLS options
        port (int) = Port number of the listening DICOM service.
        calling_ae (str): The Calling AE title.
        group (str): The DICOM tag group to use when applying tag to DICOM file.
        identifier (str): The private tag creator name to use as identification.
        tag_value (str): The value to associate the private tag with.

    Returns:
        tuple:
            dcms_present (int): The number of DICOM files for which transmission was attempted.
            dcms_sent (int): The number of DICOM files transmitted.

    """
    log.info("Downloading DICOM files.")
    dcms_sent = 0
    dcms_present = 0

    # Create input directory if it doesn't exist
    if not Path(input_dir).is_dir():
        os.mkdir(input_dir)

    # Instantiate instance connection and load acquisitions in session
    fw = get_client(api_key)
    acquisitions = fw.get(f"/api/sessions/{session_id}/acquisitions")

    # In a session, the possible downloads include any combination of:
    # zip archive, tgz archive, a single DICOM file, multiple DICOM files, or empty.
    # All cases are handled by parsing the downloaded files in the input directory
    # and calling downstream functions accordingly.
    for acq in acquisitions:
        log.debug(f"Processing acquisition {acq.label}")
        for file in acq.get("files"):
            if file.type == "dicom":

                file_path = Path(f"{input_dir}/{file.name}")
                download_file(fw, acq.id, file.name, file_path)

                if file_path.exists() and file_path.is_file():
                    present, sent = run(
                        api_key,
                        acq.id,
                        file_path,
                        work_dir,
                        destination,
                        called_ae,
                        tls,
                        port,
                        calling_ae,
                        group,
                        identifier,
                        tag_value,
                    )
                    dcms_sent += sent
                    dcms_present += present

                    # Remove contents of working directory because we assume multiple
                    # downloaded files and need a clean workspace for each run.
                    shutil.rmtree(work_dir)
                    os.mkdir(work_dir)

    if not dcms_present:
        log.error(
            "No DICOM files were available for download for session with ID: "
            f"{session_id}. The file.type must be set to dicom for download "
            "to occur. Exiting."
        )
        sys.exit(1)

    return dcms_present, dcms_sent


def run(
    api_key,
    parent_acq,
    infile,
    work_dir,
    destination,
    called_ae,
    tls: TLSOpt,
    port=104,
    calling_ae="flywheel",
    group="0x0021",
    identifier="Flywheel",
    tag_value="DICOM Send",
):
    """Run dicom-send, including tagging each DICOM file and transmitting.

    Args:
        api_key (str): The API key required to access the session in a Flywheel
            instance.
        parent_acq(str): The ID of the acquisition that the "infile" came from.
        infile (pathlib.PosixPath): The absolute path to the input file.
        work_dir (pathlib.PosixPath): The absolute path to the working directory where
            the DICOM files are placed.
        destination (str):The IP address or hostname of the destination DICOM server.
        called_ae (str):The Called AE title of the receiving DICOM server.
        tls (TLSOpt): TLS options
        port (int) = Port number of the listening DICOM service.
        calling_ae (str): The Calling AE title.
        group (str): The DICOM tag group to use when applying tag to DICOM file.
        identifier (str): The private tag creator name to use as identification.
        tag_value (str): The value to associate the private tag with.

    Returns:
        tuple:
            dcms_present (int): The number of DICOM files for which transmission was attempted.
            dcms_sent (int): The number of DICOM files transmitted.

    """
    prepare_work_dir_contents(infile, work_dir)

    dcms_present, dcms_sent = tag_and_transmit.run(
        work_dir, destination, called_ae, tls, port, calling_ae, group, identifier, tag_value
    )
    report_generator.generate_report(api_key, parent_acq, infile.name, dcms_present, dcms_sent)
    return dcms_present, dcms_sent
