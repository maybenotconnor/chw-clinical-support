"""
Streamlit Human Review UI for Clinical Guidelines.

This interface allows human reviewers to:
- View extracted documents pending review
- Inspect chunks and their metadata
- Approve or reject documents
- View raw Docling JSON output
"""

import json
import sys
from pathlib import Path

import streamlit as st

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import GuidelineDatabase


def main():
    st.set_page_config(
        page_title="CHW Guidelines Review",
        page_icon="📋",
        layout="wide"
    )

    st.title("CHW Clinical Guidelines Review")
    st.markdown("Review and approve extracted clinical guideline content.")

    # Database connection
    db_path = st.sidebar.text_input(
        "Database Path",
        value="data/databases/guidelines.db",
        help="Path to the SQLite database"
    )

    # Check if database exists
    if not Path(db_path).exists():
        st.warning(f"Database not found at: {db_path}")
        st.info("Run the extraction pipeline first to create the database.")
        st.code(
            "python -m extraction.src.pipeline data/guidelines/UCG-2023-Publication-Final-PDF-Version-1.pdf",
            language="bash"
        )
        return

    try:
        db = GuidelineDatabase(db_path)
    except Exception as e:
        st.error(f"Failed to open database: {e}")
        return

    # Sidebar: Document selection
    with st.sidebar:
        st.header("Filters")
        status_filter = st.selectbox(
            "Approval Status",
            ["all", "pending", "approved", "rejected"],
            index=1  # Default to pending
        )

        documents = db.get_documents_by_status(
            None if status_filter == "all" else status_filter
        )

        if not documents:
            st.warning("No documents found")
            return

        st.header("Documents")
        selected_doc = st.selectbox(
            "Select Document",
            documents,
            format_func=lambda d: f"{d.title[:40]}... ({d.approval_status})"
        )

    # Main content
    if selected_doc:
        display_document_review(db, selected_doc)


def display_document_review(db, doc):
    """Display document for human review."""

    # Document header
    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        st.header(doc.title or doc.filename)

    with col2:
        status_color = {
            "pending": "🟡",
            "approved": "🟢",
            "rejected": "🔴"
        }.get(doc.approval_status, "⚪")
        st.metric("Status", f"{status_color} {doc.approval_status}")

    with col3:
        chunk_count = db.get_chunk_count(doc.doc_id)
        st.metric("Chunks", chunk_count)

    # Document metadata
    with st.expander("Document Metadata", expanded=True):
        meta_col1, meta_col2 = st.columns(2)

        with meta_col1:
            st.write(f"**Filename:** {doc.filename}")
            st.write(f"**Version:** {doc.version or 'Not specified'}")

        with meta_col2:
            st.write(f"**Extracted:** {doc.extraction_date}")
            st.write(f"**Pages:** {doc.page_count}")

    # Chunks browser
    st.subheader("Extracted Chunks")

    chunks = db.get_chunks(doc.doc_id)

    if not chunks:
        st.warning("No chunks found for this document")
    else:
        # Chunk type filter
        chunk_types = list(set(c.chunk_type for c in chunks))
        selected_types = st.multiselect(
            "Filter by type",
            chunk_types,
            default=chunk_types
        )

        filtered_chunks = [c for c in chunks if c.chunk_type in selected_types]

        # Display chunks
        for i, chunk in enumerate(filtered_chunks):
            heading_text = " > ".join(chunk.headings) if chunk.headings else "No heading"

            with st.expander(
                f"**{i+1}.** {heading_text[:60]}... (p.{chunk.page_number or '?'})",
                expanded=False
            ):
                # Chunk metadata row
                meta_row = st.columns([1, 1, 2])
                with meta_row[0]:
                    st.caption(f"Type: {chunk.chunk_type}")
                with meta_row[1]:
                    st.caption(f"Page: {chunk.page_number or 'N/A'}")
                with meta_row[2]:
                    st.caption(f"Element: {chunk.element_label or 'N/A'}")

                # Full heading path
                if chunk.headings:
                    st.markdown(f"**Path:** {' > '.join(chunk.headings)}")

                # Chunk content
                st.markdown("**Content:**")
                st.text_area(
                    label="Content",
                    value=chunk.content,
                    height=150,
                    key=f"content_{chunk.chunk_id}",
                    label_visibility="collapsed"
                )

                # Contextualized text (for embedding)
                with st.expander("Contextualized Text (used for embedding)"):
                    st.text(chunk.contextualized_text)

    # Raw JSON viewer
    with st.expander("Raw Docling JSON"):
        if doc.docling_json:
            try:
                json_data = json.loads(doc.docling_json)
                st.json(json_data)
            except json.JSONDecodeError:
                st.text(doc.docling_json)
        else:
            st.info("No Docling JSON available")

    # Approval actions
    st.divider()
    st.subheader("Review Actions")

    action_col1, action_col2, action_col3 = st.columns([1, 1, 2])

    with action_col1:
        if st.button("✅ Approve", type="primary", use_container_width=True):
            db.update_approval_status(doc.doc_id, "approved")
            st.success("Document approved!")
            st.rerun()

    with action_col2:
        if st.button("❌ Reject", type="secondary", use_container_width=True):
            db.update_approval_status(doc.doc_id, "rejected")
            st.warning("Document rejected")
            st.rerun()

    with action_col3:
        if doc.approval_status != "pending":
            if st.button("🔄 Reset to Pending", use_container_width=True):
                db.update_approval_status(doc.doc_id, "pending")
                st.info("Reset to pending")
                st.rerun()


if __name__ == "__main__":
    main()
