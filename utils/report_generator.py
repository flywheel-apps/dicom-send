import logging
import os
import re
from csv import writer, reader
from datetime import datetime
from pathlib import Path
from pathvalidate import sanitize_filename

import flywheel

log = logging.getLogger(__name__)


def append_list_as_row(file_name, list_of_elem):
    """Appends a list of values to an existing or new csv file.
    
    Args:
        file_name (pathlib.PosixPath): The absolute path to the .csv file.
        list_of_elem (list): a list of elements to write to the .csv file 
    
    Returns:
        None.
    """
    # Open file in append mode
    with open(file_name, "a+", newline="") as write_obj:
        # Create a writer object from csv module
        csv_writer = writer(write_obj)
        # Add contents of list as last row in the csv file
        csv_writer.writerow(list_of_elem)


def initialize_report(file_name):
    """Initializes a report .csv file with a specified set of headers.
    
    Args:
        file_name (pathlib.PosixPath): The absolute path to the new .csv file 
    
    Returns:
        None.

    """
    header = [
        "Acquisition_ID",
        "FW_Path",
        "Filename",
        "Images_In_Series",
        "Images_Sent",
        "Status",
    ]

    append_list_as_row(file_name, header)


def make_flywheel_path(api_key, acq_id, file_name):
    """Generate a human readable path to a flywheel file.
    
    This function generates a path to a given file in the format:
    <group label>/<project label>/<subject label>/<session label>/<acquisition label>/<file name>
    The path is built using as few flywheel client calls as possible.
    
    Args:
        api_key (str): The API key required to access a Flywheel instance.
        acq_id (str): the flywheel ID of the parent acquisition of the target file.
        file_name (str): the target filename.

    Returns:
        fw_path (str): human readable string poiting to the file in the format:
    <group label>/<project label>/<subject label>/<session label>/<acquisition label>/<file name>

    """
    
    fw = flywheel.Client(api_key)
    
    acq = fw.get_acquisition(acq_id)
    ses_id = acq.session
    group = fw.get_group(acq.parents.group)
    project = group.projects.find(f"_id={acq.parents.project}")[0]
    session = project.sessions.find(f"_id={acq.parents.session}")[0]

    fw_path = (
        f"{group.label}/{project.label}/{session.subject.label}/{session.label}/"
        f"{acq.label}/{file_name}"
    )

    return fw_path


def generate_list(api_key, acq_id, file_name, DICOM_PRESENT, DICOM_SENT):
    """Generate the list of items to be appended to the report .csv for a given DICOM export
    
    The order of items in the list corresponds to the order of the headers specified in
    initialize_report()
    
    Args:
        api_key (str): The API key required to access a Flywheel instance.
        acq_id (str): the flywheel ID of the parent acquisition of the target file
        file_name (str): the name of the target file
        DICOM_PRESENT (int): the number of DICOM images present in the target file
        DICOM_SENT (int): the number of DICOM images successfully sent to the server

    Returns:
        report_list (list): The list of items to append to the report .csv file
    """

    fw_path = make_flywheel_path(api_key, acq_id, file_name)

    if DICOM_PRESENT > DICOM_SENT:
        status = "Incomplete"
    elif DICOM_PRESENT < DICOM_SENT:
        status = "Error"
    else:
        status = "Complete"

    report_list = [acq_id, fw_path, file_name, DICOM_PRESENT, DICOM_SENT, status]

    return report_list


def generate_report(
    api_key,
    acq_id,
    file_name,
    DICOMS_PRESENT,
    DICOMS_SENT,
    work_dir=Path("/flywheel/v0/report"),
):
    """Writes status information of the current DICOM upload to a report .csv file
    
    Args:
        api_key (str): The API key required to access a Flywheel instance.
        acq_id (str): the flywheel ID of the parent acquisition of the target file
        file_name (str): the name of the target file
        DICOM_PRESENT (int): the number of DICOM images present in the target file
        DICOM_SENT (int): the number of DICOM images successfully sent to the server
        work_dir (pathlib.PosixPath): The directory to generate/look for an existing report in
    
    Returns:
        None.
    """
    

    if not os.path.exists(work_dir):
        os.makedirs(work_dir)

    report_file = Path(work_dir / "dicom-send-report.csv")

    if not os.path.exists(report_file):
        log.info("Initializing report")
        initialize_report(report_file)

    log.debug("Writing to report")
    new_row = generate_list(api_key, acq_id, file_name, DICOMS_PRESENT, DICOMS_SENT)
    log.info(new_row)
    append_list_as_row(report_file, new_row)


def print_report(report_file):
    """Print the current report .csv file in a human-readable way to the log
    
    Args:
        report_file (pathlib.PosixPath): the .csv file to print

    Returns:
        None.
    """

    # This gets the lengths of each element in each row/col.  These lengths are then
    # used to format the printed output so that it's human readable.
    with open(report_file, "r", newline="") as read_obj:
        csv_f = reader(read_obj)
        lens = [[len(i) for i in row] for row in csv_f]

    max_lens = [max(idx) for idx in zip(*lens)]
    # 4 spaces are added between columns (1/2 a standard tab)
    format_string = ["{:<" + str(ml + 4) + "}" for ml in max_lens]
    format_string = " ".join(format_string) + "\n"

    with open(report_file, "r", newline="") as read_obj:
        csv_f = reader(read_obj)
        print_string = "REPORT_SUMMARY:\n"
        for row in csv_f:
            print_string += format_string.format(*row)

        log.info(print_string)


def upload_report(
    api_key,
    ses_id,
    acq_id=None,
    report_file=Path("/flywheel/v0/report/dicom-send-report.csv"),
):
    """Upload a target report .csv file to a session as an attachment
    
    Renames the report file based on the session and date.  If a single acquisition was specified
    for export, the acquisition label is included too.
    
    Args:
        api_key (str): The API key required to access a Flywheel instance.
        acq_id (str): the flywheel ID of the parent acquisition of the target file
        ses_id (str): the flywheel ID of the parent session of the target file
        report_file (pathlib.PosixPath): the name of the target file

    Returns:
        None.

    """
    
    fw = flywheel.Client(api_key)
    
    ses = fw.get_session(ses_id)
    new_name = ses.label

    if acq_id is not None:
        acq = fw.get_acquisition(acq_id)
        new_name = f"{new_name}_{acq.label}"

    timestamp = datetime.now()

    new_name = f"dicom-send_report-{new_name}_{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}.csv"
    safe_name = get_sanitized_filename(new_name)
    new_file = report_file.parent / safe_name

    os.rename(report_file, new_file)
    ses.upload_file(new_file)

    log.info(f"Report file {new_name} uploaded to session {ses.label}")
    print_report(new_file)


def get_sanitized_filename(filename):
    """A function for removing characters that are not alphanumeric, '.', '-', or '_' from an input string.
        asterix following "t2" + optional space/underscore  will be replaced with "star"
    Args:
        filename (str): an input string
    Returns:
        str: A string without characters that are not alphanumeric, '.', '-', or '_'
    """

    try:
        log
    except NameError:
        log = logging.getLogger(__name__)
    filename = re.sub(r"(t2 ?_?)\*", r"\1star", str(filename), flags=re.IGNORECASE)
    sanitized_filename = sanitize_filename(filename)
    if filename != sanitized_filename:
        log.info(f'Renaming {filename} to {sanitized_filename}')

    return sanitized_filename