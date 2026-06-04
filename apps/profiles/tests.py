from django.test import TestCase
from apps.profiles.views import normalize_board, normalize_boards_in_data

class BoardNormalizationTestCase(TestCase):
    def test_normalize_board_direct_match(self):
        # Case insensitive direct match
        val, other = normalize_board("CBSE")
        self.assertEqual(val, "CBSE")
        self.assertIsNone(other)
        
        val, other = normalize_board("cbse")
        self.assertEqual(val, "CBSE")
        self.assertIsNone(other)
        
        val, other = normalize_board("International Baccalaureate (IB)")
        self.assertEqual(val, "International Baccalaureate (IB)")
        self.assertIsNone(other)

    def test_normalize_board_mappings(self):
        # Test abbreviation / synonym mappings for IB
        val, other = normalize_board("IB")
        self.assertEqual(val, "International Baccalaureate (IB)")
        self.assertIsNone(other)
        
        val, other = normalize_board("IB-DP")
        self.assertEqual(val, "International Baccalaureate (IB)")
        self.assertIsNone(other)

        val, other = normalize_board("IB DP")
        self.assertEqual(val, "International Baccalaureate (IB)")
        self.assertIsNone(other)

        # Test CBSE
        val, other = normalize_board("CBSE Board Examination")
        self.assertEqual(val, "CBSE")
        self.assertIsNone(other)

        val, other = normalize_board("Central Board of Secondary Education")
        self.assertEqual(val, "CBSE")
        self.assertIsNone(other)

        # Test ICSE
        val, other = normalize_board("ICSE Board")
        self.assertEqual(val, "ICSE")
        self.assertIsNone(other)

        # Test ISC
        val, other = normalize_board("ISC Board")
        self.assertEqual(val, "ISC")
        self.assertIsNone(other)

        # Test NIOS
        val, other = normalize_board("National Institute of Open Schooling (NIOS)")
        self.assertEqual(val, "NIOS")
        self.assertIsNone(other)

        # Test HSC
        val, other = normalize_board("HSC Board")
        self.assertEqual(val, "HSC")
        self.assertIsNone(other)

        # Test Cambridge
        val, other = normalize_board("CIE IGCSE")
        self.assertEqual(val, "Cambridge - IGCSE")
        self.assertIsNone(other)

        val, other = normalize_board("A Levels")
        self.assertEqual(val, "Cambridge - A Levels")
        self.assertIsNone(other)

        val, other = normalize_board("Cambridge A-Level")
        self.assertEqual(val, "Cambridge - A Levels")
        self.assertIsNone(other)

        # Test American
        val, other = normalize_board("US High School Diploma")
        self.assertEqual(val, "American (AP / US High School Diploma)")
        self.assertIsNone(other)

        val, other = normalize_board("AP Physics")
        self.assertEqual(val, "American (AP / US High School Diploma)")
        self.assertIsNone(other)

        # Test State Board
        val, other = normalize_board("Maharashtra State Board")
        self.assertEqual(val, "State Board")
        self.assertIsNone(other)

        val, other = normalize_board("UPMSP")
        self.assertEqual(val, "State Board")
        self.assertIsNone(other)

        val, other = normalize_board("Board of Secondary Education, Rajasthan")
        self.assertEqual(val, "State Board")
        self.assertIsNone(other)

    def test_normalize_board_other(self):
        # Unrecognized boards should return 'Other' and the original string as other
        val, other = normalize_board("My Custom Board Name")
        self.assertEqual(val, "Other")
        self.assertEqual(other, "My Custom Board Name")
        
        val, other = normalize_board("")
        self.assertEqual(val, "Other")
        self.assertIsNone(other)

    def test_normalize_boards_in_data_recursive(self):
        # Test full recursive normalization in nested structure
        input_data = {
            "personalDetails": {"firstName": "Abhay"},
            "educational": [
                {
                    "academicLevel": "High School (8th–12th grade)",
                    "board": "IB",
                },
                {
                    "academicLevel": "High School (8th–12th grade)",
                    "board": "Maharashtra State Board",
                },
                {
                    "academicLevel": "High School (8th–12th grade)",
                    "board": "Some Unknown Board",
                }
            ]
        }
        
        expected_data = {
            "personalDetails": {"firstName": "Abhay"},
            "educational": [
                {
                    "academicLevel": "High School (8th–12th grade)",
                    "board": "International Baccalaureate (IB)",
                },
                {
                    "academicLevel": "High School (8th–12th grade)",
                    "board": "State Board",
                },
                {
                    "academicLevel": "High School (8th–12th grade)",
                    "board": "Other",
                    "boardOther": "Some Unknown Board",
                }
            ]
        }
        
        normalized = normalize_boards_in_data(input_data)
        self.assertEqual(normalized, expected_data)

