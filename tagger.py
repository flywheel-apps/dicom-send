import os
import pydicom
import argparse


class TagError(Exception):
    pass


def add_send_tag(dicomfile, group, identifier, tag_value):
    for elem_tag in range(0x0010, 0x00FF):
        dataelem = dicomfile.get((group, elem_tag))
        if dataelem:
            is_private_creator = dataelem.tag.group == group and 0x0010 <= dataelem.tag.element <= 0x00ff
            if is_private_creator and dataelem.value.lower() == identifier.lower():
                for private_tag_element in range(dataelem.tag.elem * 0x0100, dataelem.tag.elem * 0x0100 + 0x0100):
                    private_tag = (dataelem.tag.group, private_tag_element)
                    private_elem = dicomfile.get(private_tag)
                    if not private_elem:
                        dicomfile.add_new(private_tag, 'LO', tag_value)
                        return
                    elif private_elem.value.lower().startswith(tag_value.lower()):
                        return
        else:
            identifier_tag = (group, elem_tag)
            dicomfile.add_new(identifier_tag, 'LO', identifier)
            private_tag = (group, elem_tag * 0x0100)
            dicomfile.add_new(private_tag, 'LO', tag_value)
            return
    raise TagError('No free element in group {} to tag the dicom'.format(group))


def tag_image(file_path, group, identifier, tag_value):
    add_send_tag(pydicom.dcmread(file_path), group, identifier, tag_value)


def tag_folder(dir_path, group, identifier, tag_value):
    for image_file in os.listdir(dir_path):
        if '.dcm' in image_file:
            tag_image(os.path.join(dir_path, image_file), group, identifier, tag_value)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='dicom-send tag')
    parser.add_argument("dicom-input")
    parser.add_argument('--group', '-g', type=str, required=True, help='The group of the private element tag')
    parser.add_argument('--identifier', '-i', type=str, required=True, help='Identifier')
    parser.add_argument('--tag-value', '-t', type=str, required=True, help='String to tag the dicom files')

    args = parser.parse_args()

    if os.path.isdir(args.dicom_input):
        tag_folder(args.dicom_input, args.group, args.identifier, args.tag_value)
    else:
        tag_image(args.dicom_input, args.group, args.identifier, args.tag_value)
