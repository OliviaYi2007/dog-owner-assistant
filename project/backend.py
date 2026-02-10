from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
import os
from dotenv import load_dotenv
from breed_akc import get_breed_content, get_breed_list

# Load environment variables
load_dotenv()

# Initialize the LLM
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.7,
    api_key=os.getenv("OPENAI_API_KEY")
)

# Load the vectorstore you created
embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))
vectorstore = FAISS.load_local(
    "vectorstore",
    embeddings,
    allow_dangerous_deserialization=True
)

# Create a retriever
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

# Set up memory for conversation history
memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True,
    output_key="answer"
)

# Create the conversational chain
qa_chain = ConversationalRetrievalChain.from_llm(
    llm=llm,
    retriever=retriever,
    memory=memory,
    return_source_documents=True
)

def get_chatbot_response(user_question: str, selected_breed: str = None) -> str:
    """
    Get a response from the chatbot based on the user's question.
    
    Args:
        user_question: The user's question
        selected_breed: Optional normalized breed name. If provided, breed-specific
                       context from AKC will be prepended to the question.
    
    Returns:
        The chatbot's response
    """
    if selected_breed:
        breed_content = get_breed_content(selected_breed)

        print("\n==============================")
        print(f"BREED: {selected_breed}")
        print("RAW SCRAPED CONTENT (first 200000 chars):")
        print(breed_content[:2000000] if breed_content else "❌ No content")
        print("==============================\n")

    # If a breed is selected, fetch breed-specific context
    breed_context = ""
    breed_name_display = None
    
    if selected_breed:
        breed_list = get_breed_list()
        if selected_breed in breed_list:
            breed_name_display = breed_list[selected_breed]["display_name"]
            breed_content = get_breed_content(selected_breed)
            
            if breed_content:
                breed_content_limited = breed_content[:12000]
                breed_context = f"""IMPORTANT: The user is asking about a {breed_name_display}. 
Below is the official AKC (American Kennel Club) information about this breed. 
Please prioritize this breed-specific information when answering the question.

AKC Breed Information for {breed_name_display}:
{breed_content_limited}

---

Now answer the user's question with this breed-specific context in mind:
"""
    
    # Construct the enhanced question
    if breed_context:
        enhanced_question = breed_context + user_question
    else:
        enhanced_question = user_question
    
    # If question is breed-specific but no breed selected, ask for clarification
    breed_keywords = ["breed", "this dog", "my dog", "puppy", "pup"]
    is_breed_specific = any(keyword in user_question.lower() for keyword in breed_keywords)
    
    if is_breed_specific and not selected_breed:
        return "I'd be happy to help with breed-specific questions! Please select a dog breed from the sidebar to get more accurate, AKC-based answers tailored to that specific breed."
    
    # Get response from the chain
    result = qa_chain({"question": enhanced_question})
    return result["answer"]

    
