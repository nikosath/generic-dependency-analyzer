#!/usr/bin/env python3
"""
E2E test for java_dep_graph.py functionality.
Tests the complete reverse dependency analysis with specific expected output.
"""

import subprocess
import sys
from pathlib import Path
import tempfile
import os

def run_command(cmd):
    """Run command and return stdout, stderr, returncode"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=Path(__file__).parent)
    return result.stdout, result.stderr, result.returncode

def test_reverse_dependency_analysis():
    """Test reverse dependency analysis with expected output"""
    
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
    
    # Split actual output into lines and filter out empty lines
    actual_lines = [line.strip() for line in stdout.strip().split('\n') if line.strip()]
    
    # Check key requirements rather than exact line-by-line match
    success = True
    
    # Check 1: Interface and implementations are at top level (no prefix)
    interface_line = "gr.interamerican.bo.def.pc.policy.issue.bl.op.UpdateCrmOnNextDispatchTypeOperation"
    impl_lines = [
        "gr.interamerican.bo.impl.pc.policy.issue.bl.op.UpdateCrmOnNextDispatchTypeOperationImpl",
        "gr.interamerican.bo.impl.pc.interfaces.cosmos.bl.op.DoUpdateCosmosOnIssueOperationImpl",
        "gr.interamerican.one.iag.cmdm.op.DoUpdateCmdmOnIssueOperationImpl"
    ]
    
    if interface_line not in actual_lines:
        print(f"FAIL: Interface line not found: {interface_line}")
        success = False
    
    for impl in impl_lines:
        if impl not in actual_lines:
            print(f"FAIL: Implementation line not found: {impl}")
            success = False
    
    # Check 2: Level 1 dependencies exist (check for prefix pattern)
    level1_found = any(line.startswith('1- gr.interamerican.bo.def.pc.policy.dispatch.migartion.bl.op.MigratePolicyDispatchTypeOperation') for line in actual_lines)
    if not level1_found:
        print("FAIL: Level 1 MigratePolicyDispatchTypeOperation not found")
        success = False
    
    level1_found = any(line.startswith('1- gr.interamerican.bo.def.pc.policy.dispatch.op.AddNewPolicyDispatchTypeOperation') for line in actual_lines)
    if not level1_found:
        print("FAIL: Level 1 AddNewPolicyDispatchTypeOperation not found")
        success = False
    
    level1_found = any(line.startswith('1- gr.interamerican.bo.def.pc.policy.issue.bl.op.UpdateCrmOnIssueOperation') for line in actual_lines)
    if not level1_found:
        print("FAIL: Level 1 UpdateCrmOnIssueOperation not found")
        success = False
    
    # Check 3: Level 2 dependencies exist (check for prefix pattern)
    level2_patterns = [
        "2- gr.interamerican.bo.impl.pc.policy.dispatch.migartion.bl.op.MigratePolicyDispatchTypeOperationImpl",
        "2- gr.interamerican.bo.def.pc.policy.batch.bl.op.BatchUpdatePolicyDispatchTypeOperation",
        "2- gr.interamerican.bo.impl.pc.policy.batch.bl.op.BatchUpdatePolicyDispatchTypeOperationImpl",
        "2- gr.interamerican.bo.def.pc.policy.api.issue.bl.op.IssueReversedTransactionsOperation",
        "2- gr.interamerican.bo.def.pc.policy.group.issue.bl.op.CommonIssueGroupPolicyOperation"
    ]
    
    for pattern in level2_patterns:
        found = any(pattern in line for line in actual_lines)
        if not found:
            print(f"FAIL: Level 2 pattern not found: {pattern}")
            success = False
    
    # Check 4: Correct count
    count_line = "Dependents found: 28"
    if not any(count_line in line for line in actual_lines):
        print(f"FAIL: Count line not found: {count_line}")
        success = False
    
    # Check 5: Verify numbering pattern exists
    has_level1 = any(line.startswith('1- ') for line in actual_lines)
    has_level2 = any('2- ' in line for line in actual_lines)
    
    if not has_level1:
        print("FAIL: No level 1 dependencies found (1- prefix)")
        success = False
    
    if not has_level2:
        print("FAIL: No level 2 dependencies found (2- pattern)")
        success = False
    
    return success

def test_interface_implementation_siblings():
    """Test that interface implementations appear as siblings"""
    
    cmd = ('py C:/NKA/code-personal/github-repos/generic-dependency-analyzer/java_dep_graph.py '
           'C:/NKA/code/insurance-platform-3 '
           'gr.interamerican.bo.def.pc.policy.issue.bl.op.UpdateCrmOnNextDispatchTypeOperation '
           '--reverse --levels 1')
    
    stdout, stderr, returncode = run_command(cmd)
    
    if returncode != 0:
        print(f"FAIL: Command failed with return code {returncode}")
        return False
    
    # Check that interface and implementations are at same level (no prefix)
    lines = stdout.strip().split('\n')
    interface_line = "gr.interamerican.bo.def.pc.policy.issue.bl.op.UpdateCrmOnNextDispatchTypeOperation"
    impl_lines = [
        "gr.interamerican.bo.impl.pc.policy.issue.bl.op.UpdateCrmOnNextDispatchTypeOperationImpl",
        "gr.interamerican.bo.impl.pc.interfaces.cosmos.bl.op.DoUpdateCosmosOnIssueOperationImpl",
        "gr.interamerican.one.iag.cmdm.op.DoUpdateCmdmOnIssueOperationImpl"
    ]
    
    # Check interface is present
    if interface_line not in lines:
        print(f"FAIL: Interface line not found: {interface_line}")
        return False
    
    # Check all implementations are present and at same level (no prefix)
    for impl in impl_lines:
        if impl not in lines:
            print(f"FAIL: Implementation line not found: {impl}")
            return False
        # Check no prefix (should be siblings, not children)
        if impl.startswith('1- ') or impl.startswith('  '):
            print(f"FAIL: Implementation should not have prefix: {impl}")
            return False
    
    print("PASS: Interface and implementations are siblings at same level")
    return True

def main():
    """Run all E2E tests"""
    print("Running E2E tests for java_dep_graph.py...")
    
    tests = [
        ("Reverse Dependency Analysis", test_reverse_dependency_analysis),
        ("Interface-Implementation Siblings", test_interface_implementation_siblings)
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
