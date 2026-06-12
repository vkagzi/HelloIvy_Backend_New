from django.test import SimpleTestCase
from apps.profiles.views import (
    normalize_board,
    normalize_degree,
    normalize_test_type,
    normalize_level,
    normalize_grounded_dropdowns
)

class BoardNormalizationTestCase(SimpleTestCase):
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

        # Test MYP
        val, other = normalize_board("MYP")
        self.assertEqual(val, "MYP")
        self.assertIsNone(other)

        val, other = normalize_board("IB MYP")
        self.assertEqual(val, "MYP")
        self.assertIsNone(other)

        # Test IBCP
        val, other = normalize_board("IBCP")
        self.assertEqual(val, "IBCP")
        self.assertIsNone(other)

        val, other = normalize_board("IB-CP")
        self.assertEqual(val, "IBCP")
        self.assertIsNone(other)

    def test_normalize_board_other(self):
        val, other = normalize_board("My Custom Board Name")
        self.assertEqual(val, "Other")
        self.assertEqual(other, "My Custom Board Name")
        
        val, other = normalize_board("")
        self.assertEqual(val, "Other")
        self.assertIsNone(other)

    def test_normalize_degree(self):
        val, other = normalize_degree("BTech")
        self.assertEqual(val, "B.T. (Bachelor of Technology)")
        self.assertIsNone(other)

        val, other = normalize_degree("Bachelor of Business Administration")
        self.assertEqual(val, "B.B.A. (Bachelor of Business Administration)")
        self.assertIsNone(other)

        val, other = normalize_degree("MBA")
        self.assertEqual(val, "M.B.A. (Master of Business Administration)")
        self.assertIsNone(other)

        val, other = normalize_degree("Random Custom Degree")
        self.assertEqual(val, "Other")
        self.assertEqual(other, "Random Custom Degree")

    def test_normalize_test_type(self):
        val, other = normalize_test_type("EA")
        self.assertEqual(val, "Executive Assessment")
        self.assertIsNone(other)

        val, other = normalize_test_type("gmat focus")
        self.assertEqual(val, "GMAT")
        self.assertIsNone(other)

        val, other = normalize_test_type("Something Else")
        self.assertEqual(val, "Other")
        self.assertEqual(other, "Something Else")

    def test_normalize_level(self):
        self.assertEqual(normalize_level("AS"), "AS Level")
        self.assertEqual(normalize_level("HL"), "Higher (HL)")
        self.assertEqual(normalize_level("unknown"), "Not Applicable")

    def test_normalize_grounded_dropdowns_recursive(self):
        input_data = {
            "educational": [
                {
                    "board": "IB-DP",
                    "degree": "BTech"
                },
                {
                    "board": "IB-MYP",
                    "degree": "MBA"
                }
            ],
            "testScores": [
                {
                    "testType": "EA"
                }
            ],
            "subjects": [
                {
                    "level": "HL"
                }
            ]
        }
        
        expected_data = {
            "educational": [
                {
                    "board": "International Baccalaureate (IB)",
                    "degree": "B.T. (Bachelor of Technology)"
                },
                {
                    "board": "MYP",
                    "degree": "M.B.A. (Master of Business Administration)"
                }
            ],
            "testScores": [
                {
                    "testType": "Executive Assessment"
                }
            ],
            "subjects": [
                {
                    "level": "Higher (HL)"
                }
            ]
        }
        
        normalized = normalize_grounded_dropdowns(input_data)
        self.assertEqual(normalized, expected_data)
