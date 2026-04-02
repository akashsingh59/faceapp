import { useState } from "react";
import { sendMessage } from "./api/api";

function App() {
  const [input, setInput] = useState("");
  const [response, setResponse] = useState<any>(null);

  const handleSend = async () => {
    const data = await sendMessage(input);
    setResponse(data);
  };

  return (
    <div style={{ padding: 20 }}>
      <h1>FastAPI + React Test</h1>

      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Type something"
      />

      <button onClick={handleSend}>Send</button>

      {response && (
        <div>
          <p>Original: {response.original}</p>
          <p>Upper: {response.upper}</p>
          <p>Length: {response.length}</p>
        </div>
      )}
    </div>
  );
}

export default App;