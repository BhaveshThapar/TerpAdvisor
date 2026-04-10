import re

def test_regex():
    # The regex from the code
    grade_token = r'(?:A[+-]?|B[+-]?|C[+-]?|D[+-]?|F|NC|XF|W|S|P|I|TR|NG)'
    
    compact_bare = re.compile(r'^([A-Z]{3,4}\d{3}[A-Z0-9X]{0,2})\s+(' + grade_token + r')\s*(\d+\.\d{2})?$')
    
    tr_match_re = re.compile(r'^([\w\s&/-]+?)\s+(A[+-]?|B[+-]?|C[+-]?|D[+-]?|F|S|P|TR|XF|I|NG|W|AU)\s+(\d+(?:\.\d{1,2})?)(.*)$')

    test_lines = [
        "MATH141 TR 4.00",
        "CMSC330 XF 3.00",
        "CMSC351 W 3.00"
    ]

    for line in test_lines:
        print(f"\nLine: {line}")
        cb = compact_bare.match(line)
        if cb:
            print(f"  compact_bare match: GROUP1={cb.group(1)}, GROUP2={cb.group(2)}, GROUP3={cb.group(3)}")
        else:
            print("  compact_bare: NO MATCH")
            
        tm = tr_match_re.match(line)
        if tm:
            print(f"  tr_match match: GROUP1={tm.group(1)}, GROUP2={tm.group(2)}, GROUP3={tm.group(3)}")
        else:
            print("  tr_match: NO MATCH")

if __name__ == "__main__":
    test_regex()
