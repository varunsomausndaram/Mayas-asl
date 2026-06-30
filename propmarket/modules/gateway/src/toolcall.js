'use strict';
/**
 * Tool-calling normalisation layer.
 *
 * Native tool-calling (OpenAI / Anthropic via LiteLLM / capable local models):
 *   Pass tools array as-is and return the response unchanged.
 *
 * JSON fallback (models that ignore or error on the tools field):
 *   Strip the tools array, inject a structured-JSON system prompt that instructs
 *   the model to respond with a JSON object when it wants to call a tool.
 *   Parse the assistant's text response and reconstruct a synthetic
 *   tool_calls array so callers never see a difference.
 */

const FALLBACK_SYSTEM_INJECT = (tools) => `
You have access to the following tools. When you want to call a tool, respond with ONLY a JSON object (no markdown fences) in this exact format:
{"tool_call": {"name": "<tool_name>", "arguments": {<args as JSON object>}}}

If you do NOT need to call a tool, respond normally as plain text.

Available tools:
${JSON.stringify(tools, null, 2)}
`.trim();

/**
 * Prepare a request body for native tool-calling.
 * Returns the body unchanged — used when the provider supports native tool calls.
 */
function prepareNative(body) {
  return body;
}

/**
 * Prepare a request body for JSON-fallback tool-calling.
 * Strips the tools field and injects instructions into the system message.
 */
function prepareJsonFallback(body) {
  if (!body.tools || body.tools.length === 0) return body;

  const tools = body.tools;
  const messages = [...(body.messages || [])];

  // Inject or prepend a system message with tool instructions
  const sysIdx = messages.findIndex((m) => m.role === 'system');
  const injection = FALLBACK_SYSTEM_INJECT(tools);
  if (sysIdx >= 0) {
    messages[sysIdx] = {
      ...messages[sysIdx],
      content: messages[sysIdx].content + '\n\n' + injection,
    };
  } else {
    messages.unshift({ role: 'system', content: injection });
  }

  const patched = { ...body, messages };
  delete patched.tools;
  delete patched.tool_choice;
  return patched;
}

/**
 * Parse a JSON-fallback response and reconstruct tool_calls if the model
 * chose to call a tool.
 * Returns the response object, possibly with tool_calls injected.
 */
function parseJsonFallbackResponse(responseJson) {
  try {
    const choices = responseJson?.choices;
    if (!choices || choices.length === 0) return responseJson;

    const choice = choices[0];
    const text = choice?.message?.content;
    if (typeof text !== 'string') return responseJson;

    // Try to parse as JSON tool call
    const trimmed = text.trim();
    let parsed;
    try {
      parsed = JSON.parse(trimmed);
    } catch {
      return responseJson; // normal text response — no tool call
    }

    if (!parsed?.tool_call?.name) return responseJson;

    // Build a synthetic tool_calls structure
    const syntheticCall = {
      id: `tc_${Date.now()}`,
      type: 'function',
      function: {
        name: parsed.tool_call.name,
        arguments: JSON.stringify(parsed.tool_call.arguments || {}),
      },
    };

    const patched = JSON.parse(JSON.stringify(responseJson));
    patched.choices[0].message.tool_calls = [syntheticCall];
    patched.choices[0].message.content = null;
    patched.choices[0].finish_reason = 'tool_calls';
    return patched;
  } catch {
    return responseJson; // never break callers
  }
}

module.exports = { prepareNative, prepareJsonFallback, parseJsonFallbackResponse };
