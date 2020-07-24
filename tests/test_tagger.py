import unittest
import pydicom

import tagger


class taggerTestCase(unittest.TestCase):
    def setUp(self):
        self.group = 0x0021
        self.identifier = "Flywheel"
        self.tag_value = "DICOM Send"

    def test_add_private_tag(self):
        ds = pydicom.Dataset()
        tagger.add_private_tag(ds, self.group, self.identifier, self.tag_value)
        identifier_elem = ds.get((self.group, 0x0010))
        private_elem = ds.get((self.group, 0x1000))
        self.assertTrue(identifier_elem.value == "Flywheel")
        self.assertTrue(private_elem.value == "DICOM Send")

    def test_tagged_once(self):
        ds = pydicom.Dataset()
        tagger.add_private_tag(ds, self.group, self.identifier, self.tag_value)
        for tag in range(0x0011, 0x00FF):
            self.assertFalse(ds.get((self.group, tag)))
        # Make sure dicom is only tagged once
        tagger.add_private_tag(ds, self.group, self.identifier, self.tag_value)
        for tag in range(0x0011, 0x00FF):
            self.assertFalse(ds.get((self.group, tag)))

    def test_identifier_but_no_tag(self):
        # Test when tag isn't there but identifier is
        ds = pydicom.Dataset()
        ds.add_new((0x0021, 0x0010), "LO", "Flywheel")
        tagger.add_private_tag(ds, self.group, self.identifier, self.tag_value)
        identifier_elem = ds.get((self.group, 0x0010))
        private_elem = ds.get((self.group, 0x1000))
        self.assertTrue(identifier_elem.value == "Flywheel")
        self.assertTrue(private_elem.value == "DICOM Send")
        for tag in range(0x0011, 0x00FF):
            self.assertFalse(ds.get((self.group, tag)))

    def test_no_space_for_identifier(self):
        ds = pydicom.Dataset()
        for tag in range(0x0010, 0x00FF):
            ds.add_new((0x0021, tag), "LO", "Not Flywheel")
        self.assertRaises(
            tagger.TagError,
            tagger.add_private_tag,
            ds,
            self.group,
            self.identifier,
            self.tag_value,
        )

    def no_space_for_tag(self):
        ds = pydicom.Dataset()
        ds.add_new((0x0021, 0x0010), "LO", "Flywheel")
        for tag in range(0x1000, 0x10FF):
            ds.add_new((0x0021, tag), "LO", "Not DICOM Send")
        self.assertRaises(
            tagger.TagError,
            tagger.add_private_tag,
            ds,
            self.group,
            self.identifier,
            self.tag_value,
        )
