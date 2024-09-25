from langchain_ollama import ChatOllama

model = ChatOllama(
    model="codellama",
)

response_message = model.invoke(
    "Do you know the Solidity language?"
)

print(response_message.content)
