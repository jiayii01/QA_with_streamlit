import pandas as pd
import streamlit as st
from io import BytesIO
import PyPDF2
from typing import Dict
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoTokenizer, BertForQuestionAnswering, pipeline, AutoModelForQuestionAnswering

st.title("Question-Answering System using ROBERTA (trained on squad2)")

@st.cache_data()
def extract_text_from_pdfs(pdfs):
    df = pd.DataFrame(columns=["file", "text"])
    # Iterate over the PDF files
    for pdf in pdfs:
        # Open the PDF file
        with BytesIO(pdf.read()) as f:

            pdf_reader = PyPDF2.PdfReader(f)
            num_pgs = len(pdf_reader.pages)
            text = ""
            # Iterate over all the pages
            for page_num in range(num_pgs):
                # Get the page object
                page = pdf_reader.pages[page_num]
                # Extract the text from the page
                page_text = page.extract_text()
                # Add the page text to the overall text
                text += page_text
            df = pd.concat([df, pd.DataFrame({"file": pdf.name, "text": text}, index=[0])])

    return df

def preprocess_text(text_list):
    # Initialize a empty list to store the pre-processed text
    processed_text = []
    # Iterate over the text in the list
    for text in text_list:
        num_words = len(text.split(" "))
        if num_words > 10:  # only include sentences with length >10
            processed_text.append(text)
    # Return the pre-processed text
    return processed_text

# def remove_short_sentences(df):
#     df["sentences"] = df["sentences"].apply(preprocess_text)
#     return df

@st.cache_resource()
def get_relevant_texts(df, topic):
    model_embedding = SentenceTransformer("all-MiniLM-L6-v2")
    model_embedding.save("all-MiniLM-L6-v2")
    cosine_threshold = 0.3  # set threshold for cosine similarity value
    queries = topic  # search query
    results = []
    query_embedding = model_embedding.encode(queries)
    for i, document in enumerate(df["sentences"]):
        sentence_embeddings = model_embedding.encode(document)
        for j, sentence_embedding in enumerate(sentence_embeddings):
            distance = cosine_similarity(
                sentence_embedding.reshape((1, -1)), query_embedding.reshape((1, -1))
            )[0][0]
            sentence = df["sentences"].iloc[i][j]
            results += [(i, sentence, distance)]
    results = sorted(results, key=lambda x: x[2], reverse=True)
    del model_embedding

    texts = []
    for idx, sentence, distance in results:
        if distance > cosine_threshold:
            text = sentence
            texts.append(text)
    # turn the list to string
    context = "".join(texts)
    return context

@st.cache_resource()
def get_pipeline():
    model_name = "deepset/roberta-base-squad2"
    # model_name = "deepset/bert-base-cased-squad2"
    # model_name = "deepset/electra-base-squad2"
    qa_model = AutoModelForQuestionAnswering.from_pretrained(model_name)
    # qa_model = BertForQuestionAnswering.from_pretrained(model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    qa = pipeline("question-answering", model=qa_model, tokenizer=tokenizer)
    return qa

def answer_question(pipeline, question: str, context: str) -> Dict:
    input = {"question": question, "context": context}
    return pipeline(input)

@st.cache_data()
def create_context(df):
    df["sentences"] = df["text"].apply(
        lambda long_str: long_str.replace("\n", " ").split(".")
    )
    df["sentences"] = df["sentences"].apply(preprocess_text)

    context = get_relevant_texts(df, topic)
    return context

@st.cache_data()
def start_app():
    with st.spinner("Loading model. Please wait..."):
        pipeline = get_pipeline()
    return pipeline


pdf_files = st.file_uploader(
    "Upload PDF files", type=["pdf"], accept_multiple_files=True
)

if pdf_files:
    with st.spinner("Processing PDF..."):
        df = extract_text_from_pdfs(pdf_files)

    topic = st.text_input("🔎 What topic are you searching for?")
    question = st.text_input("💭 What is your question?")

    if question != "":
        with st.spinner("Searching. Please hold..."):
            context = create_context(df)
            qa_pipeline = start_app()
            answer = answer_question(qa_pipeline, question, context)
            st.write(answer)
        del qa_pipeline
        del context