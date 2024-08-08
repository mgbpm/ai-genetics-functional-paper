import os

from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack import Document
from haystack.components.preprocessors import DocumentSplitter, DocumentCleaner
from haystack import Pipeline
from haystack.components.writers import DocumentWriter
from haystack.components.embedders import SentenceTransformersDocumentEmbedder, SentenceTransformersTextEmbedder
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever, InMemoryEmbeddingRetriever
from haystack.components.joiners.document_joiner import DocumentJoiner
from haystack.components.rankers import TransformersSimilarityRanker

from utils import file_utils


class ContentRetriever:
    def __init__(self, embedding_model_name: str, reranking_model_name: str):
        document_store = InMemoryDocumentStore(embedding_similarity_function="cosine")
        self.preprocessing_pipeline = self.__create_preprocessing_pipeline(document_store, embedding_model_name)
        self.search_pipeline = self.__create_search_pipeline(document_store, embedding_model_name, reranking_model_name)

    def __create_preprocessing_pipeline(self, document_store, embedder_model: str):
        cleaner = DocumentCleaner(
            remove_empty_lines=True,
            remove_extra_whitespaces=True,
            remove_repeated_substrings=True)
        # splitter = DocumentSplitter(
        #     split_by="passage",
        #     split_length=2,
        #     split_overlap=1,
        #     split_threshold=1)
        splitter = DocumentSplitter(
            split_by="sentence",
            split_length=10,
            split_overlap=2,
            split_threshold=3)
        embedder = SentenceTransformersDocumentEmbedder(model=embedder_model)
        writer = DocumentWriter(document_store)

        pipeline = Pipeline()
        pipeline.add_component(instance=cleaner, name="cleaner")
        pipeline.add_component(instance=splitter, name="splitter")
        pipeline.add_component(instance=embedder, name="embedder")
        pipeline.add_component(instance=writer, name="writer")

        pipeline.connect("cleaner", "splitter")
        pipeline.connect("splitter", "embedder")
        pipeline.connect("embedder", "writer")

        return pipeline

    def __create_search_pipeline(self, document_store,
                                 text_embedder_model: str,
                                 reranker_model: str):
        pipeline = Pipeline()

        text_embedder = SentenceTransformersTextEmbedder(model=text_embedder_model)
        dense_retriever = InMemoryEmbeddingRetriever(document_store=document_store)
        sparse_retriever = InMemoryBM25Retriever(document_store=document_store)
        # TODO: add score_threshold to ranker
        ranker = TransformersSimilarityRanker(model=reranker_model)

        # Add components to your pipeline
        pipeline.add_component("text_embedder", text_embedder)
        pipeline.add_component("embedding_retriever", dense_retriever)
        pipeline.add_component("sparse_retriever", sparse_retriever)
        pipeline.add_component("joiner", DocumentJoiner())
        pipeline.add_component("ranker", ranker)

        # Now, connect the components to each other
        pipeline.connect("text_embedder", "embedding_retriever")
        pipeline.connect("embedding_retriever", "joiner")
        pipeline.connect("sparse_retriever", "joiner")
        pipeline.connect("joiner", "ranker")

        return pipeline

    def process_document(self, doc_text: str):
        docs = [Document(content=doc_text, meta={"name": "academic_paper"})]
        self.preprocessing_pipeline.run({"cleaner": {"documents": docs}})

    def search_query(self, retrieval_query: str, reranking_query: str, top_k: int = 5):
        result = self.search_pipeline.run({"text_embedder": {"text": retrieval_query},
                                           "embedding_retriever": {"top_k": top_k * 2},
                                           "sparse_retriever": {"query": retrieval_query, "top_k": top_k * 2},
                                           "ranker": {"query": reranking_query, "top_k": top_k}})
        return result["ranker"]["documents"]


# Usage Example
if __name__ == "__main__":
    pdf_path = "Data_efficient_unsupervised_im.pdf"
    pdf_filepath = file_utils.find_most_similar_pdf(pdf_path, ".")
    # logging.debug(f'Finding pdf_filepath: {pdf_filepath}')

    pdf_in_text = file_utils.convert_pdf_to_txt(pdf_filepath)
    query = "Masked AutoEncoder"

    analyzer = ContentRetriever(
        embedding_model_name="Snowflake/snowflake-arctic-embed-m-v1.5",
        reranking_model_name="BAAI/bge-reranker-large"
    )

    analyzer.process_document(pdf_in_text)
    top_k = 10
    search_results = analyzer.search_query(query, top_k=top_k)

    print(len(search_results))
    for doc in search_results:
        print(f"Content: {doc.content}\nScore: {doc.score}\n")
