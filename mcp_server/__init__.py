"""
MCP server — exposes rm_bridge as MCP tools for Claude and other clients.

Tools (Phase 3):
    push_pdf(path)              → push PDF to device
    pull_document(name)         → pull annotated PDF
    list_documents()            → list all documents
    render_annotations(name)    → render .rm strokes onto PDF
"""
