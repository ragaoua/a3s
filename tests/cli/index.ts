import {
  type BeforeArgs,
  type CallInterceptor,
  ClientFactory,
  ClientFactoryOptions,
  JsonRpcTransport,
} from "@a2a-js/sdk/client";
import type { MessageSendParams, Part } from "@a2a-js/sdk";
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

class AccessTokenInterceptor implements CallInterceptor {
  constructor(private readonly accessToken: string) {}

  async before(args: BeforeArgs): Promise<void> {
    args.options = {
      ...args.options,
      serviceParameters: {
        ...args.options?.serviceParameters,
        Authorization: `Bearer ${this.accessToken}`,
      },
    };
  }

  async after(): Promise<void> {}
}

async function main() {
  const port = env.PORT ?? "8000";
  const apiKey = env.API_KEY;
  const accessToken = env.ACCESS_TOKEN;
  if (apiKey && accessToken) {
    console.error("Set only one of API_KEY or ACCESS_TOKEN");
    return 1;
  }

  const interceptor: CallInterceptor | undefined = apiKey
    ? new ApiKeyInterceptor(apiKey)
    : accessToken
      ? new AccessTokenInterceptor(accessToken)
      : undefined;
  const factory = new ClientFactory(
    ClientFactoryOptions.createFrom(ClientFactoryOptions.default, {
      clientConfig: {
        interceptors: interceptor ? [interceptor] : [],
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

    process.stdout.write("Agent: ");
    let wroteResponse = false;

    for await (const event of client.sendMessageStream(sendParams)) {
      if (event.kind === "artifact-update" && !event.lastChunk) {
        const chunk = event.artifact.parts
          .filter((part) => part.kind === "text")
          .map((part) => part.text ?? "")
          .join("");
        process.stdout.write(chunk);
        wroteResponse = true;
      }

      if (event.contextId !== undefined) {
        contextId = event.contextId;
      }
    }

    if (!wroteResponse) {
      process.stdout.write("<empty response>");
    }
    process.stdout.write("\n");

    process.stdout.write("User: ");
  }
}

await main();
