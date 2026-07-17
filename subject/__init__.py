"""The evolving Customer Operations Agent subject.

Machine-readable source files (tool_registry.yaml, data_catalog.yaml, ...) describe
what the business agent can do at each capability generation. The modules here load
those files through typed schemas, build an immutable capability graph, diff
generations to find newly introduced source-to-sink paths, and turn high-risk paths
into red objectives + benign regression cases.
"""
