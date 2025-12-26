#!/usr/bin/env python3
"""
Real E2E test that compares actual output with expected output file.
Tests the complete reverse dependency analysis output against a known good reference.
"""

import subprocess
import sys
from pathlib import Path

def run_command(cmd):
    """Run command and return stdout, stderr, returncode"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=Path(__file__).parent)
    return result.stdout, result.stderr, result.returncode

def test_complete_output_match():
    """Test that actual output exactly matches expected output file"""
    
    # Command to test
    cmd = ('py C:/NKA/code-personal/github-repos/generic-dependency-analyzer/java_dep_graph.py '
           'C:/NKA/code/insurance-platform-3 '
           'gr.interamerican.bo.def.pc.policy.issue.bl.op.UpdateCrmOnNextDispatchTypeOperation '
           '--reverse --levels 2')
    
    # Run the command
    stdout, stderr, returncode = run_command(cmd)
    
    # Check command succeeded
    if returncode != 0:
        print(f"FAIL: Command failed with return code {returncode}")
        print(f"STDERR: {stderr}")
        return False
    
    # Read expected output file
    expected_file = Path(__file__).parent / 'DoUpdateCosmosOnIssueOperationImpl-expected-output.txt'
    if not expected_file.exists():
        print(f"FAIL: Expected output file not found: {expected_file}")
        return False
    
    expected_content = expected_file.read_text(encoding='utf-8').strip()
    
    # Filter out log messages from actual output
    actual_lines = []
    for line in stdout.strip().split('\n'):
        line = line.rstrip()  # Remove trailing whitespace but keep leading spaces
        if line.startswith('Loaded import'):
            continue  # Skip log messages
        actual_lines.append(line)
    
    actual_content = '\n'.join(actual_lines)
    
    # Compare actual vs expected
    if actual_content == expected_content:
        print("PASS: Actual output exactly matches expected output")
        return True
    else:
        print("FAIL: Actual output does not match expected output")
        
        # Show first few differences
        expected_lines = expected_content.split('\n')
        actual_lines_split = actual_content.split('\n')
        
        differences_found = False
        max_lines = min(len(expected_lines), len(actual_lines_split))
        
        for i in range(max_lines):
            if expected_lines[i] != actual_lines_split[i]:
                print(f"\nFirst difference at line {i+1}:")
                print(f"  Expected: '{expected_lines[i]}'")
                print(f"  Actual:   '{actual_lines_split[i]}'")
                differences_found = True
                break
        
        if not differences_found:
            if len(expected_lines) != len(actual_lines_split):
                print(f"\nLine count difference:")
                print(f"  Expected: {len(expected_lines)} lines")
                print(f"  Actual:   {len(actual_lines_split)} lines")
        
        return False

def main():
    """Run the real E2E test"""
    print("Running Real E2E test for java_dep_graph.py...")
    
    tests = [
        ("Complete Output Match", test_complete_output_match)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n=== {test_name} ===")
        try:
            if test_func():
                print(f"PASS: {test_name}")
                passed += 1
            else:
                print(f"FAIL: {test_name}")
        except Exception as e:
            print(f"ERROR: {test_name} - {e}")
    
    print(f"\n=== Results ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed!")
        return 1

if __name__ == '__main__':
    sys.exit(main())
