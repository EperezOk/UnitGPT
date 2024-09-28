from langchain_ollama import ChatOllama

model = ChatOllama(
    model="llama3.1:8b",
)

response_message = model.invoke(
    "Can you create a basic ERC20 contract with all the methods implemented?"
)

print(response_message.content)
