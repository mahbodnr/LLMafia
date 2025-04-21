from langchain_ollama import ChatOllama

llm = ChatOllama(
    model = "deepseek-r1:70b",
    temperature = 0.8,
    num_predict = 256,
    base_url = "http://gate0.neuro.uni-bremen.de:11434",
)

messages = [
    ("system", "You are a helpful translator. Translate the user sentence to French."),
    ("human", "I love programming."),
]
r = llm.invoke(messages)

print(r)