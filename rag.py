"""Funciones de RAG compartidas por los escalones 2 y 3 (LlamaIndex + Chroma)."""
import re
from pathlib import Path

import chromadb
from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.vector_stores.chroma import ChromaVectorStore

from llm import BASE, CONFIG, embed_model

DATA = BASE / "data"
SALIDAS = BASE / "salidas"
CHROMA = SALIDAS / "chroma"


def docs_reglamento() -> list[Document]:
    """Un documento por artículo del reglamento, con el número de artículo como metadato."""
    texto = (DATA / "reglamento_ley29733_extracto.md").read_text(encoding="utf-8")
    partes = re.split(r"^## ", texto, flags=re.M)[1:]
    docs = []
    for parte in partes:
        titulo, _, cuerpo = parte.partition("\n")
        m = re.match(r"Artículo (\d+)\.\s*(.*)", titulo)
        if not m:
            continue
        cuerpo = re.sub(r"^# .*$", "", cuerpo, flags=re.M).strip()
        docs.append(Document(text=f"{titulo}\n{cuerpo}",
                             metadata={"fuente": f"Art. {m.group(1)}", "titulo": m.group(2)}))
    return docs


def docs_politica() -> list[Document]:
    """Políticas de Andina Pagos YA ANONIMIZADAS por el escalón 1."""
    carpeta = SALIDAS / "anonimizado"
    archivos = sorted(carpeta.glob("*.md")) if carpeta.exists() else []
    if not archivos:
        raise SystemExit("No hay documentos anonimizados. Ejecuta primero: python escalon_1_anonimizar.py")
    return [Document(text=a.read_text(encoding="utf-8"), metadata={"fuente": a.stem}) for a in archivos]


def indice(nombre: str, documentos, reconstruir: bool = False) -> VectorStoreIndex:
    """Crea (o reutiliza) un índice vectorial persistente en salidas/chroma."""
    CHROMA.mkdir(parents=True, exist_ok=True)
    cliente = chromadb.PersistentClient(path=str(CHROMA))
    cfg = CONFIG["embeddings"]
    firma = f"{cfg['provider']}:{cfg[cfg['provider'] + '_model']}"
    try:  # si cambiaste de modelo de embeddings, el índice anterior ya no sirve
        if cliente.get_collection(nombre).metadata.get("embeddings") != firma:
            reconstruir = True
    except Exception:
        pass
    if reconstruir:
        try:
            cliente.delete_collection(nombre)
        except Exception:
            pass
    coleccion = cliente.get_or_create_collection(nombre, metadata={"embeddings": firma})
    store = ChromaVectorStore(chroma_collection=coleccion)
    emb = embed_model()
    if coleccion.count() > 0:
        return VectorStoreIndex.from_vector_store(store, embed_model=emb)
    docs = documentos() if callable(documentos) else documentos
    # El reglamento ya viene por artículo; las políticas se cortan por secciones del Markdown.
    pasos = [MarkdownNodeParser(), SentenceSplitter(chunk_size=700, chunk_overlap=80)]
    print(f"  Indexando '{nombre}' ({len(docs)} documentos)... la primera vez puede tardar un par de minutos.")
    return VectorStoreIndex.from_documents(docs, storage_context=StorageContext.from_defaults(vector_store=store),
                                           embed_model=emb, transformations=pasos)


def buscar(idx: VectorStoreIndex, consulta: str, k: int = 4) -> list[dict]:
    """Devuelve los k fragmentos más parecidos a la consulta, con su fuente."""
    resultados = idx.as_retriever(similarity_top_k=k).retrieve(consulta)
    return [{"texto": r.node.get_content(), "fuente": r.node.metadata.get("fuente", "?"),
             "puntaje": round(r.score or 0, 3)} for r in resultados]


def contexto(fragmentos: list[dict]) -> str:
    return "\n\n".join(f"[{f['fuente']}]\n{f['texto']}" for f in fragmentos)
