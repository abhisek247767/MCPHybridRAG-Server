"""Index the .txt/.md files in documents/ into the local Chroma database.

Run: uv run mcphybridrag-ingest
"""

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from mcphybridrag_server.rag import DOCUMENTS_DIR, EMBEDDING_MODEL, get_vectorstore

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=80,
)


def main() -> None:
    documents = []

    for path in sorted(DOCUMENTS_DIR.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".txt", ".md"}:
            text = path.read_text(encoding="utf-8")

            documents.append(
                Document(
                    page_content=text,
                    metadata={"source": path.name},
                )
            )

    if not documents:
        raise SystemExit(f"No .txt or .md documents found in {DOCUMENTS_DIR}")

    chunks = splitter.split_documents(documents)

    # Rebuild the local index on every ingestion run.
    vectorstore = get_vectorstore()
    existing_ids = vectorstore.get()["ids"]
    if existing_ids:
        vectorstore.delete(ids=existing_ids)

    vectorstore.add_documents(chunks)

    print(
        f"Indexed {len(chunks)} chunks from {len(documents)} file(s) "
        f"with {EMBEDDING_MODEL}."
    )


if __name__ == "__main__":
    main()
