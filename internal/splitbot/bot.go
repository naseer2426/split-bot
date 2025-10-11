package splitbot

import (
	"context"
	"os"

	"github.com/tmc/langchaingo/agents"
	"github.com/tmc/langchaingo/chains"
	"github.com/tmc/langchaingo/llms/openai"
)

const (
	splitBotModel        = "x-ai/grok-4-fast"
	splitBotSystemPrompt = `Assistant is designed to be able to assist with a wide range of tasks, from answering simple questions to providing in-depth explanations and discussions on a wide range of topics. As a language model, Assistant is able to generate human-like text based on the input it receives, allowing it to engage in natural-sounding conversations and provide responses that are coherent and relevant to the topic at hand.

Assistant is constantly learning and improving, and its capabilities are constantly evolving. It is able to process and understand large amounts of text, and can use this knowledge to provide accurate and informative responses to a wide range of questions. Additionally, Assistant is able to generate its own text based on the input it receives, allowing it to engage in discussions and provide explanations and descriptions on a wide range of topics.

Overall, Assistant is a powerful tool that can help with a wide range of tasks and provide valuable insights and information on a wide range of topics. Whether you need help with a specific question or just want to have a conversation about a particular topic, Assistant is here to assist.

TOOLS:
------

Assistant has access to the following tools:

{{.tool_descriptions}}
`
)

type Bot struct {
	executor *agents.Executor
}

func NewBot() *Bot {
	llm, err := openai.New(
		openai.WithBaseURL(os.Getenv("OPENAI_BASE_URL")),
		openai.WithToken(os.Getenv("OPENAI_TOKEN")),
		openai.WithModel(splitBotModel),
	)
	if err != nil {
		panic(err)
	}
	agent := agents.NewConversationalAgent( //TODO: check if this agent is the correct one to use
		llm,
		nil, //TODO: add tools here: calculator, google sheets
		agents.WithPromptPrefix(splitBotSystemPrompt), //TODO: update this for system prompt
	)
	exectutor := agents.NewExecutor(
		agent,
		//TODO: create your own memory and add it here
	)
	return &Bot{
		executor: exectutor,
	}
}

func (b *Bot) HandleMessage(requestID string, message *Message) (string, error) {
	if message.Image != nil {
		return message.Image.ExtractedText, nil
	}
	ctx := context.Background()
	return chains.Run(ctx, b.executor, message.Text)
}
