import flywheel
import argparse
import os


def get_dicoms(fw, session, input_dir):
    acquisitions = fw.get_session_acquisitions(session)
    if not os.path.exists(input_dir):
        os.makedirs(input_dir)
    for acq in acquisitions:
        for file_ in acq.get("files", []):
            if file_.type == "dicom":
                fw.download_file_from_acquisition(
                    acq.id, file_.name, "{}/{}".format(input_dir, file_.name)
                )


def main():
    # Read in arguments
    parser = argparse.ArgumentParser(description="BIDS Curation")
    parser.add_argument(
        "--api-key", dest="api_key", action="store", required=True, help="API key"
    )

    parser.add_argument(
        "--session",
        dest="session",
        action="store",
        required=False,
        default=None,
        help="Session Id to grab dicoms from",
    )
    parser.add_argument(
        "--input_dir",
        dest="input_dir",
        action="store",
        required=False,
        default=None,
        help="Folder to place dicoms in",
    )
    args = parser.parse_args()

    # Prep
    # Check API key - raises Error if key is invalid
    fw = flywheel.Flywheel(args.api_key)
    user = fw.get_current_user()
    if user.root:
        print("Using site admin priviledges to download")
        fw = flywheel.Flywheel(args.api_key, root=True)

    # Download dicoms
    get_dicoms(fw, args.session, args.input_dir)


if __name__ == "__main__":
    main()
