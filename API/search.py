from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_openai import ChatOpenAI
from langchain.agents import  Tool
from langgraph.prebuilt import create_react_agent
import os

# from dotenv import load_dotenv
#
# # Load environment variables from .env file
# load_dotenv(os.getcwd() + '//.env')

# Initialize OpenAI language model
llm = ChatOpenAI(temperature=0)

# Initialize Google Serper API wrapper
search = GoogleSerperAPIWrapper()

# Define tools for the agent
tools = [
    Tool(
        name="Search",
        func=search.run,
        description="Useful for when you need to answer questions about current events or the current state of the world. Input should be a search query."
    )
]

# Initialize the agent with React agent type
graph = create_react_agent(llm, tools=tools)
# Run the agent with a query

def get_result(industry):
    query = """give me a short 2-3 sentence snippet of what happened in news today
                    for {} industry that affected the stock performance today?""".format(industry)
    inputs = {"messages": [("user", query)]}
    stream = graph.stream(inputs, stream_mode="values")
    for s in stream:
        message = s["messages"][-1]
        if isinstance(message, tuple):
            print(message)
        else:
            message.pretty_print()
    return message.content

