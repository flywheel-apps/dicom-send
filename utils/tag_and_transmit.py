"""Functions to tag and transmit DICOM files as part of the dicom-send Gear."""

import logging
import backoff
import os
import subprocess
from pathlib import Path

import pydicom


log = logging.getLogger(__name__)

class TemporaryFailure(Exception):
    pass


def run(
    work_dir,
    destination,
    called_ae,
    port=104,
    calling_ae="flywheel",
    group="0x0021",
    identifier="Flywheel",
    tag_value="DICOM Send",
    pm=False
):
    """Run tag and transmit for each DICOM file in the working directory.

    Args:
        work_dir (pathlib.PosixPath): The absolute path to the working directory where
            the DICOM files are placed.
        destination (str):The IP address or hostname of the destination DICOM server.
        called_ae (str):The Called AE title of the receiving DICOM server.
        port (int) = Port number of the listening DICOM service.
        calling_ae (str): The Calling AE title.
        group (str): The DICOM tag group to use when applying tag to DICOM file.
        identifier (str): The private tag creator name to use as identification.
        tag_value (str): The value to associate the private tag with.
        pm (bool): "promiscuous mode", attempt to send DICOMS with unrecognized SOPs


    Returns:
        DICOMS_SENT (int): The number of DICOM files transmitted.

    """
    dicoms_sent = 0
    dicoms_present = 0

    for path in Path(work_dir).rglob("*"):

        if path.is_file():

            # If DICOM file, then proceed, otherwise, continue to next item in directory
            try:
                pydicom.dcmread(path, force=True)
            except pydicom.errors.InvalidDicomError:
                continue
            
            dicoms_present += 1
            
            # Tag the DICOM file so it is not re-reaped
            dicom_file, private_tag = add_private_tag(
                pydicom.dcmread(path, force=True), group, identifier, tag_value
            )
            log.info(f"DICOM file {path.name} has been successfully tagged.")
            dicom_file.save_as(path)

            # Check if the SOPClassUID is recognized
            try:
                SOPClassUID = dicom_file[0x008, 0x0016].value
            except KeyError:
                log.error(
                    f"Transmission of DICOM file {path.name} not "
                    "attempted. Unable to establish SOPClassUID."
                )
                continue

            if isinstance(SOPClassUID, type("pydicom.uid.UID")):
                # Transmit DICOM file to server specified
                try:
                    dicom_transmitted = transmit_dicom_file(
                        path, destination, called_ae, port, calling_ae, pm
                    )
                except TemporaryFailure:
                    log.error('Could not export '+path.name)

            if dicom_transmitted:
                dicoms_sent += 1

    return dicoms_present, dicoms_sent

@backoff.on_exception(backoff.expo, TemporaryFailure, max_time=60)
def transmit_dicom_file(
    dicom_file_path, destination, called_ae, port=104, calling_ae="flywheel", pm=False
):
    """Transmit DICOM file to specified receiving server.

    Args:
        dicom_file_path (pathlib.PosixPath): The absolute path to the DICOM file to
            be transmitted.
        destination (str):The IP address or hostname of the destination DICOM server.
        called_ae (str):The Called AE title of the receiving DICOM server.
        port (int) = Port number of the listening DICOM service.
        calling_ae (str): The Calling AE title.
        pm (bool): "promiscuous mode", attempt to send DICOMS with unrecognized SOPs


    Returns:
        dicom_transmitted (bool): TWhether the DICOM file was transmitted successfully.

    Raises:
        TemporaryFailure: If there is a temporary failure in the storescu command.
    """
    log.info("Begin DICOM file transfer.")
    dicom_transmitted = False

    # Create command
    command = ["storescu"]
    command.append("-v")
    command.append("--scan-directories")

    if pm:
        command.append("-pm")

    command.append("-aet")
    command.append(calling_ae)
    command.append("-aec")
    command.append(called_ae)
    command.append(destination)
    command.append(str(port))
    command.append(str(dicom_file_path))

    log_command = " ".join(command)
    log.info(f"Command to be executed: \n\n{log_command}\n")

    # Transmit DICOM file via DCMTK's storescu
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        log.error(
            f"Transmission of DICOM file {dicom_file_path.name} using DCMTK's "
            f"storescu failed with return code {process.returncode}."
        )
        log.error(f"STDERR: {stderr}")
        # Unfortunately storescu doesn't return specific error codes, always 1 if there is an error
        # The dicom standard specifies particular numbers to return for this error:
        # http://dicom.nema.org/medical/dicom/2014c/output/chtml/part02/sect_H.4.2.2.4.html
        # But these aren't returned from storescu's stderr
        # Best way to get this is to parse stderr
        out = stderr.decode('utf-8')
        if 'Temporary Congestion' in out:
            raise TemporaryFailure()
    else:
        log.info(f"Successful transmission of DICOM file {dicom_file_path.name}.")
        dicom_transmitted = True

    return dicom_transmitted


def add_private_tag(
    dicom_file, group="0x0021", identifier="Flywheel", tag_value="DICOM Send"
):
    """Add a private tag to a DICOM file.

    Args:
        dicom_file (pydicom.FileDataset): An instance of FileDataset that represents
            a parsed DICOM file.
        group (str): The DICOM tag group to use when applying tag to DICOM file.
        identifier (str): The private tag creator name to use as identification.
        tag_value (str): The value to associate the private tag with.

    Returns:
        None.
    """
    private_tag = None
    group = int(group, 16)

    for elem_tag in range(0x0010, 0x00FF):

        data_elem = dicom_file.get((group, elem_tag))

        # If the identifier tag has been created already, we only add the tag value.
        # For example, the Flywheel reaper will add an identifier tag:
        # (0021, 0010) Private Creator               LO: 'Flywheel'
        # In this case, the tag value is 'DICOM Send'.
        # (0021, 1000) Private tag data              LO: 'DICOM Send'
        if data_elem:

            if data_elem.value.lower() == identifier.lower():

                for private_tag_element in range(
                    data_elem.tag.elem * 0x0100, data_elem.tag.elem * 0x0100 + 0x0100
                ):

                    private_tag = (data_elem.tag.group, private_tag_element)
                    private_elem = dicom_file.get(private_tag)

                    if not private_elem:
                        dicom_file.add_new(private_tag, "LO", tag_value)
                        tag_formatted = "{0:#x}, {1:#x}".format(
                            private_tag[0], private_tag[1]
                        )
                        log.info(
                            f"Tag: {tag_value} added to DICOM file at "
                            f"{tag_formatted}"
                        )
                        return dicom_file, private_tag

                    elif private_elem.value.lower().startswith(tag_value.lower()):
                        log.warning(
                            f"Tag: {tag_value} already exists in {dicom_file}. "
                            "Will continue to transmit DICOM file."
                        )
                        return dicom_file, private_tag

        # If the identifier tag has not been created, we create the identifier tag.
        # In addition, we add the tag value.
        else:
            identifier_tag = (group, elem_tag)
            dicom_file.add_new(identifier_tag, "LO", identifier)
            log.info(f"Identifier tag, {identifier}, added to DICOM file.")

            private_tag = (group, elem_tag * 0x0100)
            dicom_file.add_new(private_tag, "LO", tag_value)
            tag_formatted = "{0:#x}, {1:#x}".format(private_tag[0], private_tag[1])
            log.info(f"Tag: {tag_value} added to DICOM file at {tag_formatted}")

            return dicom_file, private_tag

    # If no tag can be added to the DICOM file, log and exit
    if private_tag is None:
        log.error("No free element in group to tag the DICOM file")
        os.sys.exit(1)
