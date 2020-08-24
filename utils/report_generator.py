import logging
import os
from csv import writer, reader
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


def append_list_as_row(file_name, list_of_elem):
    # Open file in append mode
    with open(file_name, 'a+', newline='') as write_obj:
        # Create a writer object from csv module
        csv_writer = writer(write_obj)
        # Add contents of list as last row in the csv file
        csv_writer.writerow(list_of_elem)


def initialize_report(file_name):
    header = ['Acquisition_ID',
              'FW_Path',
              'Filename',
              'Images_In_Series',
              'Images_Sent',
              'Status']

    append_list_as_row(file_name, header)


def make_flywheel_path(fw, acq_id, file_name):
    
    acq = fw.get_acquisition(acq_id)
    ses_id = acq.session
    group = fw.get_group(acq.parents.group)
    project = group.projects.find(f"_id={acq.parents.project}")[0]
    session = project.sessions.find(f"_id={acq.parents.session}")[0]
    
    fw_path = f"{group.label}/{project.label}/{session.subject.label}/{session.label}/" \
              f"{acq.label}/{file_name}"

    return(fw_path)

def generate_list(fw, acq_id, file_name, DICOM_PRESENT, DICOM_SENT):
    
    fw_path = make_flywheel_path(fw, acq_id, file_name)
    
    if DICOM_PRESENT > DICOM_SENT:
        status = 'Incomplete'
    elif DICOM_PRESENT < DICOM_SENT:
        status = 'Error'
    else:
        status = 'Complete'
    
    report_list = [acq_id, fw_path, file_name, DICOM_PRESENT, DICOM_SENT, status]
    
    return(report_list)
    


def generate_report(fw, acq_id, file_name, DICOMS_PRESENT,
                    DICOMS_SENT, work_dir=Path('/flywheel/v0/report')):
    
    if not os.path.exists(work_dir):
        os.makedirs(work_dir)
    
    report_file = Path(work_dir/'dicom-send-report.csv')
    
    if not os.path.exists(report_file):
        log.info('Initializing report')
        initialize_report(report_file)
    
    log.debug('Writing to report')
    new_row = generate_list(fw, acq_id, file_name, DICOMS_PRESENT, DICOMS_SENT)
    log.info(new_row)
    append_list_as_row(report_file, new_row)
    

def print_report(report_file):
    
    # This gets the lengths of each element in each row/col.  These lengths are then
    # used to format the printed output so that it's human readable.
    with open(report_file, 'r', newline='') as read_obj:
        csv_f = reader(read_obj)
        lens = [ [len(i) for i in row] for row in csv_f]
    
    max_lens = [max(idx) for idx in zip(*lens)]
    # 4 spaces are added between columns (1/2 a standard tab)
    format_string = ["{:<"+str(ml+4)+"}" for ml in max_lens]
    format_string = " ".join(format_string)+"\n"
        
    with open(report_file, 'r', newline='') as read_obj:
        csv_f = reader(read_obj)
        print_string = 'REPORT_SUMMARY:\n'
        for row in csv_f:
            print_string+=format_string.format(*row)
        
        log.info(print_string)


def upload_report(fw, acq_id, ses_id,
                  report_file=Path('/flywheel/v0/report/dicom-send-report.csv')):
        
    ses = fw.get_session(ses_id)
    new_name = ses.label
    
    if acq_id is not None:
        acq = fw.get_acquisition(acq_id)
        new_name = f"{new_name}_{acq.label}"
    
    timestamp = datetime.now()
    
    new_name = f"{new_name}_{timestamp.strftime('%Y-%m-%d_%H:%M:%S')}.csv"
    new_file = report_file.parent/new_name
    
    os.rename(report_file, new_file)
    ses.upload_file(new_file)
    
    log.info(f"Report file {new_name} uploaded to session {ses.label}")
    print_report(report_file)
