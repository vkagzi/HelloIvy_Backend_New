"""
Consolidated user-profile formatting for LLM prompts.

Provides a single ``format_user_profile_context()`` function that converts the
raw ``profile_json`` blob (see ``UserProfile.profile_json``) into a compact,
XML-tagged string ready for injection into any LLM system/user prompt.

The function is intentionally a **standalone pure function** — no class
instantiation required — so any module (domain_discovery, career_discovery,
etc.) can import and use it directly:

    from utils.profile_formatting import format_user_profile_context
"""

from typing import Any, Dict


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _fmt_score_percentile(score: str, percentile: str) -> str:
    """Return 'score (pctile: percentile)' if both present, else just what's available."""
    if score and percentile:
        return f"{score} (pctile: {percentile})"
    return score or percentile or ""


def _resolve_profile(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve nested profile structure (profile / profile.profile / flat)."""
    profile_data = user_profile.get("profile", user_profile)
    if isinstance(profile_data, dict) and "profile" in profile_data:
        profile_data = profile_data.get("profile", profile_data)
    return profile_data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def format_user_profile_context(user_profile: Dict[str, Any], user_name: str = "") -> str:
    """Format user profile data for inclusion in LLM prompts.

    Outputs XML-tagged sections for unambiguous parsing by any LLM:
      1. ``<personal_details>``   – Basic, Address, Family, Languages, Learning/Physical
      2. ``<educational_background>`` – Academic Level, High School, UG, PG, Working/Completed
      3. ``<courses_certifications>``
      4. ``<awards_scholarships>``
      5. ``<test_scores>``
      6. ``<professional_experience>``
      7. ``<extracurricular_activities>``
      8. ``<additional_information>`` – Degree/Domain interests + free text

    Only fields with non-null, non-empty values are emitted to keep context
    compact and grounded.
    """
    if not user_profile:
        return "No profile data available."

    profile_data = _resolve_profile(user_profile)

    sections: list[str] = []

    personal_details: dict = profile_data.get("personalDetails", {}) or {}
    educational: dict = (
        profile_data.get("educational", {})
        if isinstance(profile_data.get("educational"), dict)
        else {}
    )

    # Resolve nested section format: courses, awards, testType, and
    # per-test-type arrays may live inside the active section object
    # (e.g., educational["highSchool"]["courses"]).  Lift them to the
    # top level so downstream code works unchanged.
    _section_map = {
        "High School (8th\u201312th grade)": "highSchool",
        "College/Undergraduate": "undergraduate",
        "Postgraduate": "postgraduate",
        "Working/Completed College": "tenPlus",
    }
    _active_key = _section_map.get(educational.get("academicLevel", ""), "")
    _active_section = educational.get(_active_key) if _active_key else None
    if isinstance(_active_section, dict):
        # Lift the entries array back to the section key
        _array_key = "grades" if _active_key == "highSchool" else "degrees"
        if _array_key in _active_section:
            educational[_active_key] = _active_section[_array_key]
        # Lift shared data to the top level (only if not already present)
        for _sk in ("courses", "awards", "testScores"):
            if _sk in _active_section and _sk not in educational:
                educational[_sk] = _active_section[_sk]

    # Derive testType from testScores entries if not already present
    if not educational.get("testType"):
        _test_scores = educational.get("testScores", [])
        if isinstance(_test_scores, list):
            _derived = [s.get("testType") for s in _test_scores if isinstance(s, dict) and s.get("testType")]
            if _derived:
                educational["testType"] = _derived

    # ==================================================================
    # 1. PERSONAL
    # ==================================================================
    personal_parts: list[str] = []

    # --- 1.1 Basic Details ---
    basic_parts: list[str] = []

    if user_name:
        basic_parts.append(f"Name: {user_name}")

    dob = personal_details.get("dob", "")
    if dob:
        basic_parts.append(f"Date of Birth: {dob}")

    country_code = personal_details.get("countryCode", "")
    phone = (
        personal_details.get("phoneNumber", "")
        or personal_details.get("mobileNumber", "")
        or personal_details.get("mobile", "")
    )
    if phone:
        phone_str = f"+{country_code} {phone}" if country_code else phone
        basic_parts.append(f"Phone: {phone_str}")

    gender = personal_details.get("gender", "")
    if gender:
        basic_parts.append(f"Gender: {gender}")

    # --- 1.2 Address ---
    address_line = personal_details.get("addressline", "") or personal_details.get("addressLine", "") or personal_details.get("address", "")
    city = personal_details.get("city", "")
    zip_code = personal_details.get("zipcode", "") or personal_details.get("zipCode", "") or personal_details.get("zip", "")
    state = personal_details.get("state", "")
    country = personal_details.get("country", "")
    citizenship = personal_details.get("citizenShip", "") or personal_details.get("citizenship", "")

    address_parts: list[str] = []
    if address_line:
        address_parts.append(address_line)
    if city:
        address_parts.append(city)
    if zip_code:
        address_parts.append(zip_code)
    if state:
        address_parts.append(state)
    if country:
        address_parts.append(country)
    if address_parts:
        basic_parts.append(f"Address: {', '.join(address_parts)}")

    if citizenship and citizenship != country:
        basic_parts.append(f"Citizenship: {citizenship}")

    if basic_parts:
        personal_parts.append("Basic Details:\n" + "\n".join(basic_parts))

    # --- 1.3 Family Details ---
    family_parts: list[str] = []

    fathers_profession = personal_details.get("fathersProfession", "")
    mothers_profession = personal_details.get("mothersProfession", "")
    annual_income = personal_details.get("annualIncome", "")

    if fathers_profession:
        family_parts.append(f"Father's Profession: {fathers_profession}")
    if mothers_profession:
        family_parts.append(f"Mother's Profession: {mothers_profession}")
    if annual_income:
        is_india = (
            country.lower() in ("india",)
            or citizenship.lower() in ("india", "indian")
        )
        currency = "INR" if is_india else "USD"
        family_parts.append(f"Family Annual Income: {annual_income} {currency}")

    siblings = personal_details.get("siblings", [])
    if siblings:
        sib_strs: list[str] = []
        for sib in siblings[:5]:
            if isinstance(sib, dict):
                sib_name = sib.get("siblingName", "")
                sib_age = sib.get("siblingAge", "")
                sib_institute = sib.get("siblingInstitute", "")
                sib_occupation = sib.get("siblingOccupation", "")
                if sib_name:
                    s = sib_name
                    if sib_age:
                        s += f" (age {sib_age})"
                    if sib_institute:
                        s += f" – studying at {sib_institute}"
                    elif sib_occupation:
                        s += f" – {sib_occupation}"
                    sib_strs.append(s)
        if sib_strs:
            family_parts.append(f"Siblings: {'; '.join(sib_strs)}")

    if family_parts:
        personal_parts.append("Family Details:\n" + "\n".join(family_parts))

    # --- 1.4 Languages ---
    languages = personal_details.get("languages", [])
    if languages:
        lang_parts: list[str] = []
        for lang in languages[:10]:
            if isinstance(lang, dict):
                lang_name = lang.get("language", "")
                proficiency = lang.get("proficiency", "")
                comments = lang.get("comments", "") or lang.get("type", "")
                if lang_name:
                    s = lang_name
                    if proficiency:
                        s += f" ({proficiency})"
                    if comments:
                        s += f" – {comments}"
                    lang_parts.append(f"• {s}")
            elif lang:
                lang_parts.append(f"• {lang}")
        if lang_parts:
            personal_parts.append("Languages:\n" + "\n".join(lang_parts))

    # --- 1.5 Learning & Physical ---
    _no_learning = {"no learning difficulties", "none", "no", "n/a", "na", ""}
    _no_disability = {
        "no, i do not have any physical disability",
        "no physical disability",
        "prefer not to say",
        "none",
        "no",
        "n/a",
        "na",
        "",
    }

    learning_difficulties = personal_details.get("learningDifficulties", "")
    learning_comments = personal_details.get("learningDifficultiesComments", "")
    physical_disabilities = personal_details.get("physicalDisabilities", "")
    physical_comments = personal_details.get("physicalDisabilitiesComments", "")

    access_parts: list[str] = []
    if learning_difficulties and learning_difficulties.strip().lower() not in _no_learning:
        access_parts.append(f"Learning Difficulties: {learning_difficulties}")
        if learning_comments:
            access_parts.append(f"Learning Details: {learning_comments}")
    elif learning_comments:
        access_parts.append(f"Learning Details: {learning_comments}")

    if physical_disabilities and physical_disabilities.strip().lower() not in _no_disability:
        access_parts.append(f"Physical Disability: {physical_disabilities}")
        if physical_comments:
            access_parts.append(f"Disability Details: {physical_comments}")
    elif physical_comments:
        access_parts.append(f"Disability Details: {physical_comments}")

    if access_parts:
        personal_parts.append("Learning & Physical:\n" + "\n".join(access_parts))

    if personal_parts:
        sections.append("<personal_details>\n" + "\n\n".join(personal_parts) + "\n</personal_details>")

    # ==================================================================
    # 2. EDUCATIONAL BACKGROUND
    # ==================================================================
    edu_parts: list[str] = []

    # --- 2.1 Academic Level ---
    edu_level_parts: list[str] = []

    academic_level = educational.get("academicLevel", "") or user_profile.get("academicLevel", "")
    grade_level = educational.get("gradeLevel", "") or user_profile.get("grade", "")
    current_year = educational.get("currentYear", "") or educational.get("year", "")

    if academic_level:
        edu_level_parts.append(f"Academic Level: {academic_level}")
    if grade_level and grade_level != academic_level:
        edu_level_parts.append(f"Grade/Year: {grade_level}")
    elif current_year and not grade_level:
        edu_level_parts.append(f"Current Year: {current_year}")

    if edu_level_parts:
        edu_parts.append("Academic Level:\n" + "\n".join(edu_level_parts))

    # --- 2.2 High School ---
    high_school = educational.get("highSchool", [])
    if high_school:
        hs_section_parts: list[str] = []
        for hs in high_school:
            if not isinstance(hs, dict):
                continue
            school_name = hs.get("schoolName", "")
            hs_city = hs.get("city", "")
            year_of_comp = hs.get("yearOfCompletion", "")
            board = hs.get("curriculum", "") or hs.get("board", "")
            board_other = hs.get("boardOther", "")
            your_total = hs.get("yourTotalScore", "")
            highest_total = hs.get("highestTotalScore", "")
            red_flags = hs.get("redFlags", "")

            hs_parts: list[str] = []
            if school_name:
                hs_parts.append(f"School: {school_name}")
            if hs_city:
                hs_parts.append(f"City: {hs_city}")
            if year_of_comp:
                hs_parts.append(f"Year of Completion: {year_of_comp}")
            if board:
                board_label = board_other if board.lower() == "others" and board_other else board
                hs_parts.append(f"Board: {board_label}")
            if your_total:
                score_str = f"Total Score: {your_total}"
                if highest_total:
                    score_str += f"/{highest_total}"
                hs_parts.append(score_str)
            if red_flags and red_flags.strip():
                hs_parts.append(f"Notes/Red Flags: {red_flags}")

            if hs_parts:
                hs_section_parts.append(" | ".join(hs_parts))

            # Subjects
            subjects = hs.get("subjects", [])
            subject_rows: list[str] = []
            for subj in subjects[:10]:
                if not isinstance(subj, dict):
                    continue
                subj_name = subj.get("subject", "")
                subj_other = subj.get("otherSubjectName", "")
                subj_score = subj.get("yourTotalScore", "")
                subj_highest = subj.get("highestTotalScore", "")
                if not subj_name:
                    continue
                display_name = subj_other if subj_name.lower() == "other" and subj_other else subj_name
                s = display_name
                if subj_score:
                    s += f": {subj_score}"
                    if subj_highest:
                        s += f"/{subj_highest}"
                subject_rows.append(f"  – {s}")
            if subject_rows:
                hs_section_parts.append("Subjects:\n" + "\n".join(subject_rows))

        if hs_section_parts:
            edu_parts.append("High School:\n" + "\n".join(hs_section_parts))

    # --- 2.3 Undergraduate ---
    undergraduate = educational.get("undergraduate", [])
    if undergraduate:
        ug_section_parts: list[str] = []
        for ug in undergraduate:
            if not isinstance(ug, dict):
                continue
            ug_institution = ug.get("institutionName", "")
            ug_degree = ug.get("degree", "")
            ug_major = ug.get("major", "")
            ug_start = ug.get("startYear", "")
            ug_end = ug.get("endYear", "")
            ug_overall = ug.get("overallPercentage", "") or ug.get("overallGPA", "")
            ug_max_gpa = ug.get("maximumPossibleGPA", "") or ug.get("maximumGPA", "")
            ug_rank = ug.get("estimatedRank", "")
            ug_red_flags = ug.get("redFlags", "")

            ug_parts: list[str] = []
            if ug_institution:
                ug_parts.append(f"Institution: {ug_institution}")
            if ug_degree:
                ug_parts.append(f"Degree: {ug_degree}")
            if ug_major:
                ug_parts.append(f"Major: {ug_major}")
            if ug_start or ug_end:
                ug_parts.append(f"Undergraduate Duration: {ug_start} – {ug_end}")
            if ug_overall:
                perf = f"Overall Score/Percentage/GPA: {ug_overall}"
                if ug_max_gpa:
                    perf += f"/{ug_max_gpa}"
                ug_parts.append(perf)
            if ug_rank:
                ug_parts.append(f"Overall Class Rank: {ug_rank}")
            if ug_red_flags and ug_red_flags.strip():
                ug_parts.append(f"Notes/Red Flags: {ug_red_flags}")

            if ug_parts:
                ug_section_parts.append(" | ".join(ug_parts))

            # Year-wise scores
            years = ug.get("years", [])
            yr_rows: list[str] = []
            for i, yr in enumerate(years, 1):
                if not isinstance(yr, dict):
                    continue
                yr_score = yr.get("score", "")
                yr_highest = yr.get("highestTotalScore", "")
                if yr_score:
                    s = f"Year {i}: {yr_score}"
                    if yr_highest:
                        s += f"/{yr_highest}"
                    yr_rows.append(f"  – {s}")
            if yr_rows:
                ug_section_parts.append("Year-wise Scores:\n" + "\n".join(yr_rows))

        if ug_section_parts:
            edu_parts.append("Undergraduate:\n" + "\n".join(ug_section_parts))

    # --- 2.4 Postgraduate ---
    postgraduate = educational.get("postgraduate", [])
    if postgraduate:
        pg_section_parts: list[str] = []
        for pg in postgraduate:
            if not isinstance(pg, dict):
                continue
            pg_institution = pg.get("institutionName", "")
            pg_degree = pg.get("degree", "")
            pg_major = pg.get("major", "")
            pg_start = pg.get("startYear", "")
            pg_end = pg.get("endYear", "")
            pg_overall = pg.get("overallPercentage", "") or pg.get("overallGPA", "")
            pg_max_gpa = pg.get("maximumPossibleGPA", "") or pg.get("maximumGPA", "")
            pg_rank = pg.get("estimatedRank", "")
            pg_red_flags = pg.get("redFlags", "")

            pg_parts: list[str] = []
            if pg_institution:
                pg_parts.append(f"Institution: {pg_institution}")
            if pg_degree:
                pg_parts.append(f"Degree: {pg_degree}")
            if pg_major:
                pg_parts.append(f"Major: {pg_major}")
            if pg_start or pg_end:
                pg_parts.append(f"Postgraduate Duration: {pg_start} – {pg_end}")
            if pg_overall:
                perf = f"Overall Score/Percentage/GPA: {pg_overall}"
                if pg_max_gpa:
                    perf += f"/{pg_max_gpa}"
                pg_parts.append(perf)
            if pg_rank:
                pg_parts.append(f"Overall Class Rank: {pg_rank}")
            if pg_red_flags and pg_red_flags.strip():
                pg_parts.append(f"Notes/Red Flags: {pg_red_flags}")

            if pg_parts:
                pg_section_parts.append(" | ".join(pg_parts))

            # Year-wise scores
            pg_years = pg.get("years", [])
            pg_yr_rows: list[str] = []
            for i, yr in enumerate(pg_years, 1):
                if not isinstance(yr, dict):
                    continue
                yr_score = yr.get("score", "")
                yr_highest = yr.get("highestTotalScore", "")
                if yr_score:
                    s = f"Year {i}: {yr_score}"
                    if yr_highest:
                        s += f"/{yr_highest}"
                    pg_yr_rows.append(f"  – {s}")
            if pg_yr_rows:
                pg_section_parts.append("Year-wise Scores:\n" + "\n".join(pg_yr_rows))

        if pg_section_parts:
            edu_parts.append("Postgraduate:\n" + "\n".join(pg_section_parts))

    # --- 2.5 Working / Completed College (tenPlus) ---
    ten_plus = educational.get("tenPlus", [])
    if ten_plus:
        wp_parts: list[str] = []
        for exp in ten_plus[:5]:
            if not isinstance(exp, dict):
                continue
            area = exp.get("areaOfPractice", "")
            familiarity = exp.get("familiarity", "")
            if area:
                s = area
                if familiarity:
                    s += f" (Familiarity: {familiarity})"
                wp_parts.append(f"• {s}")
        if wp_parts:
            edu_parts.append("Working/Completed College:\n" + "\n".join(wp_parts))

    if edu_parts:
        sections.append("<educational_background>\n" + "\n\n".join(edu_parts) + "\n</educational_background>")

    # ==================================================================
    # 3. COURSES & CERTIFICATIONS
    # ==================================================================
    courses = educational.get("courses", [])
    if courses:
        course_parts: list[str] = []
        for course in courses[:5]:
            if not isinstance(course, dict):
                continue
            c_type = course.get("courseType", "")
            c_link = course.get("courseLink", "")
            c_awards = course.get("awards", "")
            c_desc = course.get("description", "")
            c_dur = course.get("duration", "")
            c_loc = course.get("location", "")

            c_row: list[str] = []
            if c_type:
                c_row.append(c_type)
            if c_dur:
                c_row.append(f"Course Duration: {c_dur}")
            if c_loc:
                c_row.append(f"Course Location: {c_loc}")
            if c_link:
                c_row.append(f"Course Link: {c_link}")
            if c_awards and c_awards.lower() not in ("none", ""):
                c_row.append(f"Course Awards: {c_awards}")
            if c_desc and c_desc.lower() not in ("none", ""):
                c_row.append(f"Course Description: {c_desc[:120]}")

            if c_row:
                course_parts.append(f"• {' | '.join(c_row)}")

        if course_parts:
            sections.append("<courses_certifications>\n" + "\n".join(course_parts) + "\n</courses_certifications>")

    # ==================================================================
    # 4. AWARDS & SCHOLARSHIPS
    # ==================================================================
    awards = educational.get("awards", [])
    legacy_achievements = user_profile.get("achievements", [])

    award_parts: list[str] = []
    for award in awards[:5]:
        if not isinstance(award, dict):
            continue
        a_name = award.get("nameOfHonorReceived", "")
        a_desc = award.get("description", "")
        a_level = award.get("levelOfCompetitiveness", "")
        a_participants = award.get("numberOfParticipants", "")
        a_year = award.get("year", "")

        a_row: list[str] = []
        if a_name:
            a_row.append(a_name)
        if a_year:
            a_row.append(f"({a_year})")
        if a_level:
            a_row.append(f"{a_level} level")
        if a_participants:
            a_row.append(f"{a_participants} participants")
        if a_desc and a_desc.lower() != "none":
            a_row.append(f"– {a_desc[:80]}")

        if a_row:
            award_parts.append(f"• {' | '.join(a_row)}")

    if isinstance(legacy_achievements, list):
        for ach in legacy_achievements[:3]:
            name = ach.get("title", ach) if isinstance(ach, dict) else str(ach)
            if name:
                award_parts.append(f"• {name}")

    if award_parts:
        sections.append("<awards_scholarships>\n" + "\n".join(award_parts) + "\n</awards_scholarships>")

    # ==================================================================
    # 5. STANDARDISED TEST SCORES
    # ==================================================================
    test_section_parts: list[str] = []

    test_types = educational.get("testType", [])
    if test_types:
        test_section_parts.append(f"Registered Tests: {', '.join(test_types)}")

    # SAT
    sat_data = educational.get("SAT", [])
    for sat in sat_data[:1]:
        if not isinstance(sat, dict):
            continue
        sat_rows: list[str] = []
        if sat.get("testDate"):
            sat_rows.append(f"Date: {sat['testDate']}")
        if sat.get("totalScore"):
            sat_rows.append(f"Total: {sat['totalScore']}")
        writing_str = _fmt_score_percentile(sat.get("writingYourScore", ""), sat.get("writingYourPercentile", ""))
        if writing_str:
            sat_rows.append(f"Writing: {writing_str}")
        math_str = _fmt_score_percentile(sat.get("mathYourScore", ""), sat.get("mathYourPercentile", ""))
        if math_str:
            sat_rows.append(f"Math: {math_str}")
        reading_str = _fmt_score_percentile(sat.get("criticalReadingYourScore", ""), sat.get("criticalReadingYourPercentile", ""))
        if reading_str:
            sat_rows.append(f"Critical Reading: {reading_str}")
        if sat.get("retakeExamDate"):
            sat_rows.append(f"Retake Date: {sat['retakeExamDate']}")
        if sat.get("numberOfAttempts"):
            sat_rows.append(f"Attempts: {sat['numberOfAttempts']}")
        if sat_rows:
            test_section_parts.append("SAT: " + " | ".join(sat_rows))

    # ACT
    act_data = educational.get("ACT", [])
    for act in act_data[:1]:
        if not isinstance(act, dict):
            continue
        act_rows: list[str] = []
        if act.get("testDate"):
            act_rows.append(f"Date: {act['testDate']}")
        if act.get("totalScore"):
            act_rows.append(f"Total: {act['totalScore']}")
        eng_str = _fmt_score_percentile(act.get("englishYourScore", ""), act.get("englishYourPercentile", ""))
        if eng_str:
            act_rows.append(f"English: {eng_str}")
        math_str = _fmt_score_percentile(act.get("mathYourScore", ""), act.get("mathYourPercentile", ""))
        if math_str:
            act_rows.append(f"Math: {math_str}")
        reading_str = _fmt_score_percentile(act.get("readingYourScore", ""), act.get("readingYourPercentile", ""))
        if reading_str:
            act_rows.append(f"Reading: {reading_str}")
        science_str = _fmt_score_percentile(act.get("scienceYourScore", ""), act.get("scienceYourPercentile", ""))
        if science_str:
            act_rows.append(f"Science: {science_str}")
        if act.get("retakeExamDate"):
            act_rows.append(f"Retake Date: {act['retakeExamDate']}")
        if act.get("numberOfAttempts"):
            act_rows.append(f"Attempts: {act['numberOfAttempts']}")
        if act_rows:
            test_section_parts.append("ACT: " + " | ".join(act_rows))

    # TOEFL
    toefl_data = educational.get("TOEFL", [])
    for toefl in toefl_data[:1]:
        if not isinstance(toefl, dict):
            continue
        toefl_rows: list[str] = []
        if toefl.get("testDate"):
            toefl_rows.append(f"Date: {toefl['testDate']}")
        score_str = _fmt_score_percentile(
            toefl.get("yourScore", "") or toefl.get("totalScore", ""),
            toefl.get("yourPercentile", ""),
        )
        if score_str:
            toefl_rows.append(f"Score: {score_str}")
        if toefl.get("numberOfAttempts"):
            toefl_rows.append(f"Attempts: {toefl['numberOfAttempts']}")
        if toefl_rows:
            test_section_parts.append("TOEFL: " + " | ".join(toefl_rows))

    # IELTS
    ielts_data = educational.get("IELTS", [])
    for ielts in ielts_data[:1]:
        if not isinstance(ielts, dict):
            continue
        ielts_rows: list[str] = []
        if ielts.get("testDate"):
            ielts_rows.append(f"Date: {ielts['testDate']}")
        score_str = _fmt_score_percentile(
            ielts.get("yourScore", "") or ielts.get("totalScore", ""),
            ielts.get("yourPercentile", ""),
        )
        if score_str:
            ielts_rows.append(f"Score: {score_str}")
        if ielts.get("numberOfAttempts"):
            ielts_rows.append(f"Attempts: {ielts['numberOfAttempts']}")
        if ielts_rows:
            test_section_parts.append("IELTS: " + " | ".join(ielts_rows))

    # GRE
    gre_data = educational.get("GRE", [])
    for gre in gre_data[:1]:
        if not isinstance(gre, dict):
            continue
        gre_rows: list[str] = []
        if gre.get("testDate"):
            gre_rows.append(f"Date: {gre['testDate']}")
        if gre.get("totalScore"):
            gre_rows.append(f"Total: {gre['totalScore']}")
        aw_str = _fmt_score_percentile(gre.get("analyticalWritingScore", ""), gre.get("analyticalWritingPercentile", ""))
        if aw_str:
            gre_rows.append(f"Analytical Writing: {aw_str}")
        verbal_str = _fmt_score_percentile(gre.get("verbalReasoningScore", ""), gre.get("verbalReasoningPercentile", ""))
        if verbal_str:
            gre_rows.append(f"Verbal: {verbal_str}")
        quant_str = _fmt_score_percentile(gre.get("quantitativeReasoningScore", ""), gre.get("quantitativeReasoningPercentile", ""))
        if quant_str:
            gre_rows.append(f"Quantitative: {quant_str}")
        if gre.get("retakeExamDate"):
            gre_rows.append(f"Retake Date: {gre['retakeExamDate']}")
        if gre.get("numberOfAttempts"):
            gre_rows.append(f"Attempts: {gre['numberOfAttempts']}")
        if gre_rows:
            test_section_parts.append("GRE: " + " | ".join(gre_rows))

    # GMAT
    gmat_data = educational.get("GMAT", [])
    for gmat in gmat_data[:1]:
        if not isinstance(gmat, dict):
            continue
        gmat_rows: list[str] = []
        if gmat.get("testDate"):
            gmat_rows.append(f"Date: {gmat['testDate']}")
        if gmat.get("totalScore"):
            gmat_rows.append(f"Total: {gmat['totalScore']}")
        di_str = _fmt_score_percentile(gmat.get("dataInsightsScore", ""), gmat.get("dataInsightsPercentile", ""))
        if di_str:
            gmat_rows.append(f"Data Insights: {di_str}")
        verbal_str = _fmt_score_percentile(gmat.get("verbalReasoningScore", ""), gmat.get("verbalReasoningPercentile", ""))
        if verbal_str:
            gmat_rows.append(f"Verbal: {verbal_str}")
        quant_str = _fmt_score_percentile(gmat.get("quantitativeReasoningScore", ""), gmat.get("quantitativeReasoningPercentile", ""))
        if quant_str:
            gmat_rows.append(f"Quantitative: {quant_str}")
        if gmat.get("retakeExamDate"):
            gmat_rows.append(f"Retake Date: {gmat['retakeExamDate']}")
        if gmat.get("numberOfAttempts"):
            gmat_rows.append(f"Attempts: {gmat['numberOfAttempts']}")
        if gmat_rows:
            test_section_parts.append("GMAT: " + " | ".join(gmat_rows))

    # Executive Assessment
    ea_data = educational.get("Executive Assessment", [])
    for ea in ea_data[:1]:
        if not isinstance(ea, dict):
            continue
        ea_rows: list[str] = []
        if ea.get("testDate"):
            ea_rows.append(f"Date: {ea['testDate']}")
        if ea.get("totalScore"):
            ea_rows.append(f"Total: {ea['totalScore']}")
        ir_str = _fmt_score_percentile(ea.get("integratedReasoningScore", ""), ea.get("integratedReasoningPercentile", ""))
        if ir_str:
            ea_rows.append(f"Integrated Reasoning: {ir_str}")
        verbal_str = _fmt_score_percentile(ea.get("verbalReasoningScore", ""), ea.get("verbalReasoningPercentile", ""))
        if verbal_str:
            ea_rows.append(f"Verbal: {verbal_str}")
        quant_str = _fmt_score_percentile(ea.get("quantitativeReasoningScore", ""), ea.get("quantitativeReasoningPercentile", ""))
        if quant_str:
            ea_rows.append(f"Quantitative: {quant_str}")
        if ea.get("retakeExamDate"):
            ea_rows.append(f"Retake Date: {ea['retakeExamDate']}")
        if ea.get("tookCoaching") == "Yes" and ea.get("coachingName"):
            ea_rows.append(f"Coaching: {ea['coachingName']}")
        if ea.get("numberOfAttempts"):
            ea_rows.append(f"Attempts: {ea['numberOfAttempts']}")
        if ea_rows:
            test_section_parts.append("Executive Assessment: " + " | ".join(ea_rows))

    # Others
    others_data = educational.get("Others", []) or educational.get("others", [])
    for other in others_data[:1]:
        if not isinstance(other, dict):
            continue
        other_rows: list[str] = []
        if other.get("testDate"):
            other_rows.append(f"Date: {other['testDate']}")
        if other.get("yourScore") or other.get("totalScore"):
            other_rows.append(f"Score: {other.get('yourScore') or other.get('totalScore')}")
        if other.get("numberOfAttempts"):
            other_rows.append(f"Attempts: {other['numberOfAttempts']}")
        if other_rows:
            test_section_parts.append("Other Test: " + " | ".join(other_rows))

    if test_section_parts:
        sections.append("<test_scores>\n" + "\n".join(test_section_parts) + "\n</test_scores>")

    # ==================================================================
    # 6. PROFESSIONAL EXPERIENCE
    # ==================================================================
    professional = profile_data.get("professional", {})
    if isinstance(professional, dict):
        experiences = professional.get("experiences", [])
        if not experiences and any(professional.values()):
            experiences = [professional]  # legacy single-object format

        prof_parts: list[str] = []
        for exp in experiences[:5]:
            if not isinstance(exp, dict):
                continue
            exp_type = exp.get("experienceType", "")
            industry = exp.get("industrySector", "") or exp.get("industry", "")
            employer = exp.get("currentEmployer", "") or exp.get("employer", "") or exp.get("companyName", "")
            exp_city = exp.get("city", "")
            duration_val = exp.get("durationValue", "") or exp.get("durationOfEmployment", "")
            duration_unit = exp.get("durationUnit", "")
            job_title = exp.get("jobTitle", "") or exp.get("yourTitle", "")
            responsibilities = exp.get("responsibilities", "") or exp.get("yourResponsibilities", "")
            reason_leaving = exp.get("reasonForLeaving", "")

            exp_row: list[str] = []
            if job_title:
                exp_row.append(f"Title: {job_title}")
            if employer:
                exp_row.append(f"Employer: {employer}")
            if industry:
                exp_row.append(f"Industry: {industry}")
            if exp_city:
                exp_row.append(f"City: {exp_city}")
            if duration_val:
                dur_str = f"{duration_val} {duration_unit}".strip()
                exp_row.append(f"Experience Duration: {dur_str}")
            if exp_type:
                exp_row.append(f"Experience Type: {exp_type}")

            if exp_row:
                prof_parts.append(f"• {' | '.join(exp_row)}")

            if responsibilities and responsibilities.strip():
                prof_parts.append(f"  Responsibilities: {responsibilities[:150]}")

            # Achievements (top 3)
            raw_achievements = exp.get("achievements", []) or exp.get("yourAchievements", [])
            if isinstance(raw_achievements, list):
                shown = 0
                for ach in raw_achievements:
                    if shown >= 3:
                        break
                    ach_text = ach.get("achievement", "") if isinstance(ach, dict) else str(ach)
                    if ach_text.strip():
                        prof_parts.append(f"  Achievement: {ach_text[:120]}")
                        shown += 1

            if reason_leaving and reason_leaving.strip():
                prof_parts.append(f"  Reason for Leaving: {reason_leaving}")

        if prof_parts:
            sections.append("<professional_experience>\n" + "\n".join(prof_parts) + "\n</professional_experience>")

    # ==================================================================
    # 7. EXTRA-CURRICULAR ACTIVITIES
    # ==================================================================
    extracurricular = profile_data.get("extraCurricular", []) or user_profile.get("extracurriculars", [])
    if extracurricular:
        ec_parts: list[str] = []
        for activity in extracurricular[:5]:
            if not isinstance(activity, dict):
                ec_parts.append(f"• {activity}")
                continue
            act_type = activity.get("activityType", "") or activity.get("name", "")
            start_date = activity.get("startDate", "")
            end_date = activity.get("endDate", "")
            position = activity.get("positionHeld", "")
            ec_awards = activity.get("awardsCertifications", "") or activity.get("awards", "") or activity.get("certifications", "")
            description = activity.get("description", "")

            act_row: list[str] = []
            if act_type:
                act_row.append(act_type)
            if start_date or end_date:
                act_row.append(f"{start_date} – {end_date}".strip(" –"))
            if position:
                act_row.append(f"Position: {position}")
            if ec_awards and ec_awards.lower() not in ("none", ""):
                act_row.append(f"Awards: {ec_awards}")
            if description and description.lower() not in ("none", ""):
                act_row.append(f"Desc: {description[:100]}")

            if act_row:
                ec_parts.append(f"• {' | '.join(act_row)}")

        if ec_parts:
            sections.append("<extracurricular_activities>\n" + "\n".join(ec_parts) + "\n</extracurricular_activities>")

    # ==================================================================
    # 8. ADDITIONAL INFORMATION
    # ==================================================================
    additional = profile_data.get("additional", {}) or {}
    add_parts: list[str] = []

    if isinstance(additional, dict):
        degree_interest = additional.get("degreeInterest", "") or additional.get("interestedProgram", "")
        if degree_interest:
            add_parts.append(f"Program/Degree Interest: {degree_interest}")

        degree_other = additional.get("degreeInterestOther", "") or additional.get("specifyProgram", "")
        if degree_other:
            add_parts.append(f"Program (specified): {degree_other}")

        degree_why = additional.get("whyInterest", "") or additional.get("degreeWhyInterest", "")
        if degree_why:
            if len(degree_why) > 300:
                degree_why = degree_why[:300] + "..."
            add_parts.append(f"Reason for Degree Interest: {degree_why}")

        domain_interest = additional.get("domainInterest", "") or additional.get("interestedDomain", "")
        if domain_interest:
            add_parts.append(f"Domain of Interest: {domain_interest}")

        domain_other = additional.get("domainInterestOther", "") or additional.get("specifyDomain", "")
        if domain_other:
            add_parts.append(f"Domain (specified): {domain_other}")

        domain_why = additional.get("domainWhyInterest", "")
        if domain_why:
            if len(domain_why) > 300:
                domain_why = domain_why[:300] + "..."
            add_parts.append(f"Reason for Domain Interest: {domain_why}")

        share_info = (
            additional.get("shareInformationDescription", "")
            or additional.get("additionalInfo", "")
            or additional.get("otherInfo", "")
        )
        if share_info and share_info.strip():
            if len(share_info) > 400:
                share_info = share_info[:400] + "..."
            add_parts.append(f"Student's Additional Notes: {share_info}")

        personal_statement = additional.get("personalStatement", "")
        if personal_statement and personal_statement.strip():
            if len(personal_statement) > 300:
                personal_statement = personal_statement[:300] + "..."
            add_parts.append(f"Personal Statement: {personal_statement}")

        career_goals = additional.get("careerGoals", "")
        if career_goals:
            add_parts.append(f"Career Aspirations: {career_goals}")

    if add_parts:
        sections.append("<additional_information>\n" + "\n".join(add_parts) + "\n</additional_information>")

    # ==================================================================
    # RETURN
    # ==================================================================
    if sections:
        return "\n\n".join(sections)

    return "No profile data available."
