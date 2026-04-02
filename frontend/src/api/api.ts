export const sendMessage = async (text: string) => {
  const res = await fetch(`${import.meta.env.VITE_API_URL}/echo`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text }),
  });

  return res.json();
};