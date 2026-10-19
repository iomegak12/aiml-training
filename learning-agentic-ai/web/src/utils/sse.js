// Minimal Server-Sent Events parser for fetch() streams.
// EventSource can't send POST bodies, so /chat-streaming is read with fetch + ReadableStream.

function parseBlock(block) {
  let event = 'message'
  const data = []
  for (const line of block.split('\n')) {
    if (!line || line.startsWith(':')) continue
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') event = value
    else if (field === 'data') data.push(value)
  }
  if (data.length === 0) return null
  const raw = data.join('\n')
  try {
    return { event, data: JSON.parse(raw) }
  } catch {
    return { event, data: raw }
  }
}

/** Yields `{ event, data }` objects from a text/event-stream response body. */
export async function* readSse(stream) {
  const reader = stream.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += value.replace(/\r\n/g, '\n')
      let boundary
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const parsed = parseBlock(buffer.slice(0, boundary))
        buffer = buffer.slice(boundary + 2)
        if (parsed) yield parsed
      }
    }
    const tail = parseBlock(buffer.trim())
    if (tail) yield tail
  } finally {
    reader.releaseLock()
  }
}
