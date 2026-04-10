import re

class ParsedCourse:
    def __init__(self, course_id, name, credits, grade, gen_eds, in_catalog, in_progress=False):
        self.course_id = course_id
        self.name = name
        self.credits = credits
        self.grade = grade
        self.gen_eds = gen_eds
        self.in_catalog = in_catalog
        self.in_progress = in_progress

def _match_courses_logic(raw_text):
    _UMD_DEPT_PREFIXES = {"MATH", "CMSC"}
    _GENED_CODES = {"FSAR", "FSMA"}
    _DROPPED_ACTIONS = {"AW", "D", "W"}
    _EXCLUDED_GRADES = {"AU"}
    _GRADE_QUALITY = {"A": 4, "B": 3, "XF": 0, "W": 0, "TR": 2}
    known_set = {"MATH141", "CMSC330", "CMSC351"}
    
    lines = raw_text.split("\n")
    seen = {}
    next_is_repeat = False
    in_progress_section = False
    _current_course_re = re.compile(r'^([A-Z]{3,4}\d{3}[A-Z0-9X]{0,2})\s+(\S+)\s+(\d+\.\d{1,2})(.*)?$')
    
    # Loop 1
    for line in lines:
        line = line.strip()
        if not line: continue
        
        if in_progress_section:
            cm = _current_course_re.match(line)
            if cm:
                course_id = cm.group(1)
                if course_id not in seen:
                    seen[course_id] = ParsedCourse(course_id, None, float(cm.group(3)), None, [], course_id in known_set, True)
            continue

        # Pattern for tabular transcript
        m = re.match(r'^([A-Z]{3,4}\d{3}[A-Z0-9X]{0,2})\s+(.+?)\s+([A-Z][+-]?|NC|XF|W|S|P|I|TR)\s+(\d+\.\d{2})\s+(\d+\.\d{2})\s+(\d+\.\d{2})(.*)?$', line)
        if m:
            course_id = m.group(1)
            grade = m.group(3)
            credits = float(m.group(4))
            seen[course_id] = ParsedCourse(course_id, m.group(2).strip(), credits, grade, [], course_id in known_set)
        else:
            _grade_token = r'(?:A[+-]?|B[+-]?|C[+-]?|D[+-]?|F|NC|XF|W|S|P|I|TR|NG)'
            compact_bare = re.match(r'^([A-Z]{3,4}\d{3}[A-Z0-9X]{0,2})\s+(' + _grade_token + r')\s*(\d+\.\d{2})?$', line)
            if compact_bare:
                course_id = compact_bare.group(1)
                seen[course_id] = ParsedCourse(course_id, None, float(compact_bare.group(3)) if compact_bare.group(3) else 0.0, compact_bare.group(2), [], course_id in known_set)
                continue

    # Loop 2
    for line in lines:
        line = line.strip()
        tr_match = re.match(r'^([\w\s&/-]+?)\s+(A[+-]?|B[+-]?|C[+-]?|D[+-]?|F|S|P|TR|XF|I|NG|W|AU)\s+(\d+(?:\.\d{1,2})?)(.*)$', line)
        if tr_match:
            m_course = tr_match.group(1).strip()
            m_grade = tr_match.group(2).strip()
            m_credits = float(tr_match.group(3))
            
            equiv_matches = re.findall(r'\b([A-Z]{3,4}\d{3}[A-Z0-9X]{0,2})\b', line)
            found_equivs = []
            is_transfer_line = "/SCR" in line.upper() or "Transfer" in line or "Advanced Placement" in line
            for cid in equiv_matches:
                if cid[:4] in _UMD_DEPT_PREFIXES and is_transfer_line:
                    found_equivs.append(cid)
                    if cid not in seen:
                        seen[cid] = ParsedCourse(cid, None, m_credits, "TR", [], cid in known_set)
            
            if m_course and m_credits is not None and not found_equivs:
                clean_name = re.sub(r'[^A-Z0-9_]', '', m_course.upper().replace(' ', '_'))
                cid = f"TR_{m_credits}_{clean_name}"
                if cid not in seen:
                    seen[cid] = ParsedCourse(cid, m_course, m_credits, m_grade, [], False)

    return seen

test_text = "CMSC330 XF 3.00\nCMSC351 W 3.00\nMATH141 TR 4.00"
result = _match_courses_logic(test_text)
print(f"Results for text:\n{test_text}\n")
for cid, c in result.items():
    print(f"ID: {cid}, Grade: {c.grade}, Credits: {c.credits}")
