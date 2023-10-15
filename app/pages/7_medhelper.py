import os
import pickle
import streamlit as st
import openai
from langchain.llms import OpenAI
from langchain import PromptTemplate
from llama_hub.file.pymu_pdf.base import PyMuPDFReader
# from llama_index import VectorStoreIndex, ServiceContext, LLMPredictor
from llama_index import download_loader

# This module is imported so that we can 
# play the converted audio
import os
from datetime import datetime

import os
from contextlib import contextmanager
from typing import Optional
from langchain.agents import tool
from langchain.tools.file_management.read import ReadFileTool
from langchain.tools.file_management.write import WriteFileTool

# General 
import os
import pandas as pd

from langchain_experimental.autonomous_agents.autogpt.agent import AutoGPT
from langchain.chat_models import ChatOpenAI

from langchain.agents.agent_toolkits.pandas.base import create_pandas_dataframe_agent
from langchain.docstore.document import Document
import asyncio
import nest_asyncio

from langchain.tools import BaseTool, DuckDuckGoSearchRun
from langchain.text_splitter import RecursiveCharacterTextSplitter

from pydantic import Field
from langchain.chains.qa_with_sources.loading import load_qa_with_sources_chain, BaseCombineDocumentsChain

# Memory
import faiss
from langchain.vectorstores import FAISS
from langchain.docstore import InMemoryDocstore
from langchain.embeddings import OpenAIEmbeddings
from langchain.tools.human.tool import HumanInputRun


@contextmanager
def pushd(new_dir):
    """Context manager for changing the current working directory."""
    prev_dir = os.getcwd()
    os.chdir(new_dir)
    try:
        yield
    finally:
        os.chdir(prev_dir)

@tool
def process_csv(
    csv_file_path: str, instructions: str, output_path: Optional[str] = None
) -> str:
    """Process a CSV by with pandas in a limited REPL.\
 Only use this after writing data to disk as a csv file.\
 Any figures must be saved to disk to be viewed by the human.\
 Instructions should be written in natural language, not code. Assume the dataframe is already loaded."""
    with pushd(ROOT_DIR):
        try:
            df = pd.read_csv(csv_file_path)
        except Exception as e:
            return f"Error: {e}"
        agent = create_pandas_dataframe_agent(llm, df, max_iterations=30, verbose=True)
        if output_path is not None:
            instructions += f" Save output to disk at {output_path}"
        try:
            result = agent.run(instructions)
            return result
        except Exception as e:
            return f"Error: {e}"

async def async_load_playwright(url: str) -> str:
    """Load the specified URLs using Playwright and parse using BeautifulSoup."""
    from bs4 import BeautifulSoup
    from playwright.async_api import async_playwright

    results = ""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(url)

            page_source = await page.content()
            soup = BeautifulSoup(page_source, "html.parser")

            for script in soup(["script", "style"]):
                script.extract()

            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            results = "\n".join(chunk for chunk in chunks if chunk)
        except Exception as e:
            results = f"Error: {e}"
        await browser.close()
    return results

def run_async(coro):
    event_loop = asyncio.get_event_loop()
    return event_loop.run_until_complete(coro)

@tool
def browse_web_page(url: str) -> str:
    """Verbose way to scrape a whole webpage. Likely to cause issues parsing."""
    return run_async(async_load_playwright(url))

def _get_text_splitter():
    return RecursiveCharacterTextSplitter(
        # Set a really small chunk size, just to show.
        chunk_size = 500,
        chunk_overlap  = 20,
        length_function = len,
    )


class WebpageQATool(BaseTool):
    name = "query_webpage"
    description = "Browse a webpage and retrieve the information relevant to the question."
    text_splitter: RecursiveCharacterTextSplitter = Field(default_factory=_get_text_splitter)
    qa_chain: BaseCombineDocumentsChain
    
    def _run(self, url: str, question: str) -> str:
        """Useful for browsing websites and scraping the text information."""
        result = browse_web_page.run(url)
        docs = [Document(page_content=result, metadata={"source": url})]
        web_docs = self.text_splitter.split_documents(docs)
        results = []
        # TODO: Handle this with a MapReduceChain
        for i in range(0, len(web_docs), 4):
            input_docs = web_docs[i:i+4]
            window_result = self.qa_chain({"input_documents": input_docs, "question": question}, return_only_outputs=True)
            results.append(f"Response from window {i} - {window_result}")
        results_docs = [Document(page_content="\n".join(results), metadata={"source": url})]
        return self.qa_chain({"input_documents": results_docs, "question": question}, return_only_outputs=True)
    
    async def _arun(self, url: str, question: str) -> str:
        raise NotImplementedError

        
def setup_agents(llm, memory):

    query_website_tool = WebpageQATool(qa_chain=load_qa_with_sources_chain(llm))

    web_search = DuckDuckGoSearchRun()

    embeddings_model = OpenAIEmbeddings()
    embedding_size = 1536
    index = faiss.IndexFlatL2(embedding_size)
    vectorstore = FAISS(embeddings_model.embed_query, index, InMemoryDocstore({}), {})
    
    tools_admin = [
        # web_search,
        # WriteFileTool(root_dir=folder),
        # ReadFileTool(root_dir=folder),
        # process_csv,
        query_website_tool,
        # HumanInputRun(), # Activate if you want the permit asking for help from the human
    ]

    
    agent_admin = AutoGPT.from_llm_and_tools(
        ai_name="LARA",
        ai_role="You are LARA, an advanced digital assistant designed specifically to help people with dementia. Individuals with dementia often face challenges in recalling memories, recognizing familiar faces, and performing daily tasks. As the condition progresses, they might also find it challenging to navigate their surroundings, remember their medication schedules, or even recollect personal history and family details.",
        tools=tools_admin,
        llm=llm,
        memory=vectorstore.as_retriever(search_kwargs={"k": 8}),
        # human_in_the_loop=True, # Set to True if you want to add feedback at each step.
    )

    return agent_admin



def load_memory():
    data_folder = 'data/'
    pickle_files = [f for f in os.listdir(data_folder) if f.endswith('.pickle')]

    context = ''

    for file in pickle_files:
        with open(os.path.join(data_folder, file), 'rb') as f:
            data = pickle.load(f)
            context += str(data)
            
    pdf_folder = 'datapdf/'
    pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith('.pdf')]

    for file in pdf_files:
        PDFReader = download_loader("PDFReader")
        loader = PDFReader()
        documents = loader.load_data(file=os.path.join(pdf_folder, file))
        # index = VectorStoreIndex.from_documents(documents)
        # index.storage_context.persist()
        context += documents[0].text

    context += f'/n {datetime.now()}'

    return context

context = load_memory()
llm = ChatOpenAI(model_name="gpt-4", temperature=0.5, max_tokens=2000)

admin = setup_agents(llm, context)

res = admin.run(["Search for the price of Aspirin."])

st.write(res)