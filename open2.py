from openai import OpenAI
client = OpenAI(api_key="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")

assistant = client.beta.assistants.create(
    name="HammaBot",
    instructions="You are an assitant in a stock trading app, named HammaBot that interacts with traders to create alert, trade stocks, provide information on trading generally.",
    tools=[{"type": "code_interpreter"}],
    model="gpt-3.5-turbo"
)

print(assistant.id)

thread = client.beta.threads.create()

print(thread.id)

message = client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content="Hello, Who are you? what is 10% of 1,500"
)

run = client.beta.threads.runs.create(
  thread_id=thread.id,
  assistant_id=assistant.id,
  instructions="Please address the user as trader."
)

messages = client.beta.threads.messages.list(
  thread_id=thread.id
)

print(messages)