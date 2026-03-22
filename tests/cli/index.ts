import {
  type BeforeArgs,
  type CallInterceptor,
  ClientFactory,
  ClientFactoryOptions,
} from "@a2a-js/sdk/client";
import type { Message, MessageSendParams, Task } from "@a2a-js/sdk";
import { v4 as uuidv4 } from "uuid";
import { env } from "bun";

class ApiKeyInterceptor implements CallInterceptor {
  constructor(private readonly apiKey: string) {}

  async before(args: BeforeArgs): Promise<void> {
    args.options = {
      ...args.options,
      serviceParameters: {
        ...args.options?.serviceParameters,
        "API-Key": this.apiKey,
      },
    };
  }

  async after(): Promise<void> {}
}

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
  const apiKey = env.API_KEY ?? "";
  const factory = new ClientFactory(
    ClientFactoryOptions.createFrom(ClientFactoryOptions.default, {
      clientConfig: {
        interceptors: apiKey ? [new ApiKeyInterceptor(apiKey)] : [],
      },
    }),
  );
  const client = await factory.createFromUrl(`http://localhost:${port}`);
  const agentCard = await client.getAgentCard();

  console.log(`Connected to A2A agent: ${agentCard.name}`);
  let contextId: string | undefined = undefined;

  process.stdout.write("User: ");
  for await (const line of console) {
    const sendParams: MessageSendParams = {
      message: {
        messageId: uuidv4(),
        role: "user",
        parts: [{ kind: "text", text: line }],
        kind: "message",
        contextId,
      },
    };

    const result = await client.sendMessage(sendParams);
    const response =
      result.kind === "task"
        ? getTaskResponse(result)
        : getMessageResponse(result);

    console.log("Agent: ", response);

    contextId = result.contextId;
    process.stdout.write("User: ");
  }
}

await main();
