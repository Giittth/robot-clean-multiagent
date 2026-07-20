export async function fetchSSE(url, body, onChunk, onDone, onError) {
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6);
          if (dataStr === '[DONE]') {
            onDone();
            continue;
          }
          try {
            const data = JSON.parse(dataStr);
            if (data.content) onChunk(data.content);
            if (data.done) onDone();
          } catch (e) {
            console.error('Parse error:', e, dataStr);
          }
        }
      }
    }
    onDone();
  } catch (error) {
    if (onError) onError(error);
    else console.error('SSE error:', error);
  }
}