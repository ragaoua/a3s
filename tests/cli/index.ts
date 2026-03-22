import { ClientFactory } from "@a2a-js/sdk/client";
import type { Message, MessageSendParams, Task } from "@a2a-js/sdk";
import { v4 as uuidv4 } from "uuid";
import { env } from "bun";

function getMessageResponse(message: Message) {
  return message.parts
    .filter((part) => part.kind === "text")
    .map((part) => part.text)
    .join("");
}

function getTaskResponse(task: Task) {
  if (task.status.state === "completed") {
    const parts = task.artifacts
      ? task.artifacts.flatMap((artifact) => artifact.parts)
      : [];
    return parts
      .filter((part) => part.kind === "text")
      .map((part) => part.text)
      .join("");
  }
  return task.status.message ?? "<empty response>";
}

async function main() {
  const port = env.PORT ?? "8000";
  const factory = new ClientFactory();
  const client = await factory.createFromUrl(`http://localhost:${port}`);
  const agentCard = await client.getAgentCard();

  console.log(`Connected to A2A agent: ${agentCard.name}`);

  process.stdout.write("User: ");
  for await (const line of console) {
    const sendParams: MessageSendParams = {
      message: {
        messageId: uuidv4(),
        role: "user",
        parts: [{ kind: "text", text: line }],
        kind: "message",
      },
    };

    const result = await client.sendMessage(sendParams);
    const response =
      result.kind === "task"
        ? getTaskResponse(result)
        : getMessageResponse(result);

    console.log("Agent: ", response);

    process.stdout.write("User: ");
  }
}

await main();
