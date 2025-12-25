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

### 2. Breadth-First Search (BFS) of Dependents
The following is an ASCII hierarchy (BFS) of dependents for
`gr.interamerican.ws.impl.exceptions.CleanseCustomerFailedException`. `-` denotes a node:
```
gr.interamerican.ws.impl.exceptions.CleanseCustomerFailedException
- gr.interamerican.bo.impl.pc.interfaces.cosmos.services.op.NormalizeAddressOperationImpl
- gr.interamerican.bo.impl.pc.interfaces.cosmos.services.op.NormalizeCustomerOperationImpl
- gr.interamerican.ws.impl.customer.CleanseCustomerClient
  - gr.interamerican.bo.def.pc.interfaces.cosmos.bl.op.AddOrRetrieveCustomerOperation
    - gr.interamerican.bo.impl.pc.interfaces.cosmos.bl.op.AddOrRetrieveCustomerOperationImpl
Dependents found: 5 
```

### Handle of implements/extends relationships
When a class implements an interface or extends a superclass, those should be treated as nodes of the same level as the class that implements or extends them.