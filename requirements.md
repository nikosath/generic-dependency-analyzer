# Requirements/specifications for java_dep_graph.py
The script `java_dep_graph.py` must produce results matching the following specifications.

## Guidelines for ASCII hierarchy representation
Indentation should be exactly two spaces per level.

## 1. Reverse Dependents Search

### 1. Depth-First Search (DFS) of Dependents
The following is an ASCII hierarchy (DFS) of dependents for
`gr.interamerican.ws.impl.exceptions.CleanseCustomerFailedException`. `|-` denotes a node:
```
gr.interamerican.ws.impl.exceptions.CleanseCustomerFailedException
|- gr.interamerican.bo.impl.pc.interfaces.cosmos.services.op.NormalizeAddressOperationImpl
|- gr.interamerican.bo.impl.pc.interfaces.cosmos.services.op.NormalizeCustomerOperationImpl
  |- gr.interamerican.bo.def.pc.interfaces.cosmos.bl.op.AddOrRetrieveCustomerOperation
    |- gr.interamerican.bo.impl.pc.interfaces.cosmos.bl.op.AddOrRetrieveCustomerOperationImpl
|- gr.interamerican.ws.impl.customer.CleanseCustomerClient
Dependents found: 5 
```

### Handle of implements/extends relationships
When a class implements an interface or extends a superclass, those should be treated as nodes of the same level as the class that implements or extends them.

### Implemented-interface siblings
When a class implements an interface, the implemented interface MUST be presented as a sibling of the implementing class at the same indentation level (not as a child). Example:

|- gr.interamerican.bo.impl.pc.interfaces.cosmos.bl.op.ScheduleCosmosUpdateOnIssueOperationImpl
|- gr.interamerican.bo.def.pc.policy.issue.bl.op.UpdateCrmOnIssueOperation

Rationale: given a class declaration like:

public abstract class ScheduleCosmosUpdateOnIssueOperationImpl
extends AbstractOperation
implements UpdateCrmOnIssueOperation {

the interface `UpdateCrmOnIssueOperation` should be treated as a sibling node at the same level as `ScheduleCosmosUpdateOnIssueOperationImpl`.

### Implementation-Interface Sibling Rule
When an implementation class directly imports a target class, if the implementation class implements an interface, both the implementation class AND its interface must appear as siblings at the same level.

Example: Given `MigratePolicyDispatchTypeOperationImpl` imports `UpdateCrmOnNextDispatchTypeOperation` and implements `MigratePolicyDispatchTypeOperation`, the results should show:

|- gr.interamerican.bo.impl.pc.policy.dispatch.migartion.bl.op.MigratePolicyDispatchTypeOperationImpl
|- gr.interamerican.bo.def.pc.policy.dispatch.migartion.bl.op.MigratePolicyDispatchTypeOperation

Rationale: The implementation class is a direct dependent through import, and its interface should be treated as a sibling dependency at the same level since the implementation cannot exist without its interface.